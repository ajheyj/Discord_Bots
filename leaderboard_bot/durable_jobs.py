"""SQLite job state machine. No downloads/OCR/Discord awaits inside transactions."""
import json
import time
from datetime import datetime,timezone

ACTIVE=('download_wait','downloading','ready','ocr_running','ocr_retry')
class QueueRejected(ValueError):pass

class DurableJobs:
    def __init__(self,store,config,clock=time.time):
        self.store,self.db,self.config,self.clock=store,store.db,config,clock
        self.db.executescript('''CREATE TABLE IF NOT EXISTS queue_jobs(
          message TEXT PRIMARY KEY,user TEXT NOT NULL,author_name TEXT NOT NULL,url TEXT NOT NULL,
          created_at TEXT NOT NULL,attachments TEXT NOT NULL,replay INTEGER NOT NULL,
          state TEXT NOT NULL,added REAL NOT NULL,updated REAL NOT NULL,next_at REAL NOT NULL,
          download_attempts INTEGER NOT NULL DEFAULT 0,ocr_attempts INTEGER NOT NULL DEFAULT 0,
          reserved INTEGER NOT NULL,spooled INTEGER NOT NULL DEFAULT 0,error TEXT,
          finished REAL,notified INTEGER NOT NULL DEFAULT 0);
          CREATE INDEX IF NOT EXISTS queue_ready ON queue_jobs(state,next_at,added);
          CREATE INDEX IF NOT EXISTS queue_user ON queue_jobs(user,state);''')
        columns={r[1] for r in self.db.execute('PRAGMA table_info(queue_jobs)')}
        for name in ('notify_after','notify_attempts'):
            if name not in columns:self.db.execute('ALTER TABLE queue_jobs ADD COLUMN '+name+' INTEGER NOT NULL DEFAULT 0')
        self.db.executescript('''CREATE INDEX IF NOT EXISTS queue_retention ON queue_jobs(state,finished) WHERE reserved>0;
            CREATE INDEX IF NOT EXISTS queue_notifications ON queue_jobs(notify_after,finished)
            WHERE notified=0 AND state IN ('done','failed');
            CREATE INDEX IF NOT EXISTS queue_reserved ON queue_jobs(spooled,reserved) WHERE reserved>0;''')
        if 'source_channel' not in columns:self.db.execute('ALTER TABLE queue_jobs ADD COLUMN source_channel TEXT')
        self.db.commit()

    def rows(self,sql,params=()):
        cursor=self.db.execute(sql,params)
        return [dict(zip([c[0] for c in cursor.description],row)) for row in cursor.fetchall()]
    def get(self,message):
        rows=self.rows('SELECT * FROM queue_jobs WHERE message=?',(str(message),))
        return rows[0] if rows else None
    def reserved(self):
        return self.db.execute('SELECT COALESCE(sum(reserved),0) FROM queue_jobs WHERE reserved>0').fetchone()[0]
    def outstanding(self):
        return self.db.execute('SELECT COALESCE(sum(reserved),0) FROM queue_jobs WHERE spooled=0 AND reserved>0').fetchone()[0]

    def admit(self,message,user,author_name,url,created_at,attachments,replay,free_bytes,source_channel=None):
        if self.store.seen(message):return False
        now=self.clock();old=self.get(message)
        if old and str(user)!=old['user']:raise QueueRejected('Original uploader does not match the saved job.')
        if old and (old['state']!='failed' or not replay):return False
        required=sum(a['size'] for a in attachments)
        # An existing failed job retains its original attachment snapshot and identity.
        if old:
            attachments=json.loads(old['attachments']);required=sum(a['size'] for a in attachments)
        extra=max(0,required-(old['reserved'] if old else 0))
        with self.db:
            count=self.db.execute("SELECT count(*) FROM queue_jobs WHERE state IN ('download_wait','downloading','ready','ocr_running','ocr_retry')").fetchone()[0]
            users=self.db.execute("SELECT count(*) FROM queue_jobs WHERE user=? AND state IN ('download_wait','downloading','ready','ocr_running','ocr_retry')",(str(user),)).fetchone()[0]
            if count>=self.config.max_jobs:raise QueueRejected('The durable queue is full. Please submit again later.')
            if users>=self.config.per_user:raise QueueRejected('You already have the maximum number of pending submissions. Wait for them to finish.')
            if self.reserved()+extra>self.config.spool_bytes or self.outstanding()+extra>free_bytes-self.config.min_free_bytes:
                raise QueueRejected('Image storage is full or reserved. Please submit again later; no new job was accepted.')
            if old:
                self.db.execute('''UPDATE queue_jobs SET state=?,updated=?,next_at=?,download_attempts=0,
                    ocr_attempts=0,reserved=?,error=NULL,finished=NULL,notified=0,notify_after=0,notify_attempts=0,replay=1 WHERE message=?''',
                    ('ready' if old['spooled'] else 'download_wait',now,now,required,str(message)))
            else:
                self.db.execute('''INSERT INTO queue_jobs(message,user,author_name,url,created_at,attachments,
                    replay,state,added,updated,next_at,reserved) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (str(message),str(user),author_name,url,created_at,json.dumps(attachments),int(replay),'download_wait',now,now,now,required))
            if source_channel is not None:self.db.execute('UPDATE queue_jobs SET source_channel=? WHERE message=?',(str(source_channel),str(message)))
        return True

    def claim(self,stage):
        if stage not in ('download','ocr'):raise ValueError('Invalid queue stage')
        states=('download_wait',) if stage=='download' else ('ready','ocr_retry')
        active='downloading' if stage=='download' else 'ocr_running'
        counter='download_attempts' if stage=='download' else 'ocr_attempts'
        while True:
            now=self.clock()
            candidates=self.rows('SELECT * FROM queue_jobs WHERE state IN ('+','.join('?' for _ in states)+') AND next_at<=? ORDER BY added,message LIMIT 1',(*states,now))
            if not candidates:return None
            row=candidates[0]
            if row[counter]>=self.config.attempts:
                self.fail(row['message'],'Attempt limit reached; this job could not complete safely.')
                continue
            with self.db:
                changed=self.db.execute('UPDATE queue_jobs SET state=?,updated=?,'+counter+'='+counter+'+1 WHERE message=? AND state=?',
                    (active,now,row['message'],row['state'])).rowcount
            if changed:return self.get(row['message'])

    def ready(self,message):
        with self.db:self.db.execute("UPDATE queue_jobs SET state='ready',spooled=1,updated=?,next_at=? WHERE message=?",(self.clock(),self.clock(),str(message)))
    def release_files(self,message):
        with self.db:self.db.execute('UPDATE queue_jobs SET reserved=0,spooled=0 WHERE message=?',(str(message),))
    def retry(self,message,stage,reason):
        row=self.get(message);counter='download_attempts' if stage=='download' else 'ocr_attempts'
        if row[counter]>=self.config.attempts:return False
        delay=min(3600,self.config.retry_delay*2**max(0,row[counter]-1))
        with self.db:self.db.execute('UPDATE queue_jobs SET state=?,error=?,updated=?,next_at=? WHERE message=?',
            ('download_wait' if stage=='download' else 'ocr_retry',reason,self.clock(),self.clock()+delay,str(message)))
        return True
    def succeed(self,message,values):
        row=self.get(message)
        with self.db:
            if not self.store.seen(message):
                self.store.record(message,row['user'],row['author_name'],row['url'],values,
                    submitted_at=datetime.fromisoformat(row['created_at']),transaction=False)
            self.db.execute("UPDATE queue_jobs SET state='done',updated=?,finished=?,notified=0,error=NULL WHERE message=?",(self.clock(),self.clock(),str(message)))
    def fail(self,message,reason):
        if self.store.seen(message):
            self.succeed(message,{})
            return
        row=self.get(message)
        with self.db:
            self.store.record(message,row['user'],row['author_name'],row['url'],error=reason,transaction=False)
            self.db.execute("UPDATE queue_jobs SET state='failed',error=?,updated=?,finished=?,notified=0 WHERE message=?",(reason,self.clock(),self.clock(),str(message)))
    def recover(self,stale_before=None):
        params=() if stale_before is None else (stale_before,)
        condition='' if stale_before is None else ' AND updated<?'
        rows=self.rows("SELECT * FROM queue_jobs WHERE state IN ('downloading','ocr_running')"+condition,params)
        with self.db:
            for row in rows:
                state='ready' if row['spooled'] else 'download_wait'
                self.db.execute('UPDATE queue_jobs SET state=?,next_at=?,updated=? WHERE message=?',(state,self.clock(),self.clock(),row['message']))
        return rows
    def notifications(self):
        return self.rows("SELECT * FROM queue_jobs WHERE state IN ('done','failed') AND notified=0 AND notify_after<=? ORDER BY finished LIMIT 20",(self.clock(),))
    def notified(self,message):
        with self.db:self.db.execute('UPDATE queue_jobs SET notified=1 WHERE message=?',(str(message),))
    def counts(self):
        return dict(self.db.execute('SELECT state,count(*) FROM queue_jobs GROUP BY state').fetchall())
    def oldest(self):
        return self.db.execute("SELECT min(added) FROM queue_jobs WHERE state IN ('download_wait','downloading','ready','ocr_running','ocr_retry')").fetchone()[0]

    def notification_retry(self,message):
        row=self.get(message)
        delay=min(600,60*2**min(row['notify_attempts'],4))
        with self.db:self.db.execute('UPDATE queue_jobs SET notify_after=?,notify_attempts=notify_attempts+1 WHERE message=?',
            (self.clock()+delay,str(message)))
    def need_download(self,message):
        with self.db:self.db.execute("UPDATE queue_jobs SET state='download_wait',spooled=0,next_at=?,updated=? WHERE message=?",(self.clock(),self.clock(),str(message)))
