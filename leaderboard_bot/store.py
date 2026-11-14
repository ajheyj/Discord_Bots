import sqlite3,json
from datetime import datetime,timezone
from pathlib import Path
from contextlib import nullcontext

STAT_KEYS=('packs','money','coins','shiny','playtime')

class Store:
    def __init__(self,path):
        if not str(path).strip() or str(path).strip()==':memory:':
            raise ValueError('DATABASE_PATH must name a persistent database file.')
        self.path=Path(path).resolve()
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path,timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA busy_timeout=10000')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS scores(user TEXT PRIMARY KEY,name TEXT,packs TEXT,money TEXT,coins TEXT);
        CREATE TABLE IF NOT EXISTS audit(message TEXT PRIMARY KEY,user TEXT,url TEXT,time TEXT,status TEXT,details TEXT);
        CREATE TABLE IF NOT EXISTS boards(category TEXT PRIMARY KEY,message TEXT);
        CREATE TABLE IF NOT EXISTS admin_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,user TEXT NOT NULL,time TEXT NOT NULL,action TEXT NOT NULL,
        category TEXT,before_values TEXT NOT NULL,after_values TEXT NOT NULL,reason TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS admin_delivery(audit_id INTEGER PRIMARY KEY,delivered_message TEXT);
        CREATE TABLE IF NOT EXISTS submission_failures(id INTEGER PRIMARY KEY AUTOINCREMENT,
        message TEXT NOT NULL,user TEXT NOT NULL,url TEXT NOT NULL,time TEXT NOT NULL,
        reason TEXT NOT NULL,delivered_message TEXT,UNIQUE(message,reason));''')
        # Additive migration: keep every existing Discord-keyed score and audit.
        columns={row[1] for row in self.db.execute('PRAGMA table_info(scores)')}
        for key in ('shiny','playtime'):
            if key not in columns:self.db.execute('ALTER TABLE scores ADD COLUMN '+key+' TEXT')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS player_profiles(
            user TEXT PRIMARY KEY,epic_name TEXT NOT NULL,observed_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS player_names(user TEXT,name TEXT,first_seen TEXT,last_seen TEXT,
            PRIMARY KEY(user,name));''')
        self.db.executescript("""CREATE TABLE IF NOT EXISTS submission_results(
            message TEXT PRIMARY KEY,user TEXT NOT NULL,url TEXT NOT NULL,time TEXT NOT NULL,
            payload TEXT NOT NULL,delivered_message TEXT,dm_status TEXT);
            CREATE TABLE IF NOT EXISTS dm_sessions(user TEXT PRIMARY KEY,expires REAL NOT NULL);""")
        self.db.commit()

    def seen(self,message):
        return self.db.execute('SELECT 1 FROM audit WHERE message=? AND status="ok"',(str(message),)).fetchone() is not None
    def record(self,message,user,name,url,values=None,error=None,submitted_at=None,transaction=True):
        if error is not None:
            prior=self.db.execute('SELECT status,details FROM audit WHERE message=?',(str(message),)).fetchone()
            if prior==('failed',error):return
        numeric={key:value for key,value in (values or {}).items() if key in STAT_KEYS}
        if values and (not numeric or any(type(v) is not int or v<0 for v in numeric.values())):
            raise ValueError('Provide at least one nonnegative integer statistic.')
        epic=(values or {}).get('username')
        if epic is not None and (not isinstance(epic,str) or not 1<=len(epic.strip())<=64):
            raise ValueError('Invalid Epic display name.')
        timestamp=submitted_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None:timestamp=timestamp.replace(tzinfo=timezone.utc)
        observed=timestamp.astimezone(timezone.utc).isoformat(timespec='microseconds')
        with (self.db if transaction else nullcontext()):
            before=self.score_values(user)
            if numeric:
                old=self.db.execute('SELECT '+','.join(STAT_KEYS)+' FROM scores WHERE user=?',(str(user),)).fetchone()
                vals=[]
                for i,key in enumerate(STAT_KEYS):
                    previous=int(old[i]) if old and old[i] is not None else None
                    new=numeric.get(key)
                    value=max(previous,new) if previous is not None and new is not None else previous if new is None else new
                    vals.append(str(value) if value is not None else None)
                self.db.execute('''INSERT OR REPLACE INTO scores(user,name,packs,money,coins,shiny,playtime)
                    VALUES(?,?,?,?,?,?,?)''',(str(user),name,*vals))
                if epic:
                    self.db.execute('''INSERT INTO player_names VALUES(?,?,?,?) ON CONFLICT(user,name)
                        DO UPDATE SET first_seen=min(first_seen,excluded.first_seen),last_seen=max(last_seen,excluded.last_seen)''',
                        (str(user),epic,observed,observed))
                    self.db.execute('''INSERT INTO player_profiles VALUES(?,?,?) ON CONFLICT(user) DO UPDATE
                        SET epic_name=excluded.epic_name,observed_at=excluded.observed_at
                        WHERE excluded.observed_at>=player_profiles.observed_at''',(str(user),epic,observed))
            self.db.execute('INSERT OR REPLACE INTO audit VALUES(?,?,?,?,?,?)',(str(message),str(user),url,datetime.now(timezone.utc).isoformat(),'ok' if numeric else 'failed',json.dumps(values) if numeric else error))
            payload={'recognized':numeric,'before':before,'after':self.score_values(user),
                     'username':epic,'warnings':(values or {}).get('_warnings',[]),'error':error if not numeric else None}
            self.db.execute("""INSERT INTO submission_results(message,user,url,time,payload) VALUES(?,?,?,?,?)
                ON CONFLICT(message) DO UPDATE SET payload=excluded.payload,time=excluded.time,
                delivered_message=NULL,dm_status=NULL""",
                (str(message),str(user),url,datetime.now(timezone.utc).isoformat(),json.dumps(payload)))
            if not numeric:
                self.db.execute('''INSERT OR IGNORE INTO submission_failures(message,user,url,time,reason)
                    VALUES(?,?,?,?,?)''',(str(message),str(user),url,datetime.now(timezone.utc).isoformat(),str(error or 'Submission failed.')[:500]))

    def ranked(self,key):
        if key not in STAT_KEYS:raise ValueError(key)
        rows=self.db.execute('SELECT s.user,COALESCE(p.epic_name,s.name),s.'+key+
            ' FROM scores s LEFT JOIN player_profiles p ON p.user=s.user WHERE s.'+key+' IS NOT NULL').fetchall()
        return sorted([(u,n,int(v)) for u,n,v in rows],key=lambda row:(-row[2],int(row[0])))

    def identity(self,user):
        row=self.db.execute('SELECT epic_name FROM player_profiles WHERE user=?',(str(user),)).fetchone()
        return row[0] if row else None

    def board(self,key):
        row=self.db.execute('SELECT message FROM boards WHERE category=?',(key,)).fetchone()
        return int(row[0]) if row else None
    def save_board(self,key,message):
        with self.db: self.db.execute('INSERT OR REPLACE INTO boards VALUES(?,?)',(key,str(message)))

    def admin_change(self,actor,user,reason,category=None,value=None):
        """Override an existing entry and append its audit row atomically."""
        if not isinstance(reason,str) or not 1 <= len(reason.strip()) <= 300:
            raise ValueError('Provide a reason between 1 and 300 characters.')
        if category is not None:
            if category not in STAT_KEYS:
                raise ValueError('Unknown category.')
            if type(value) is not int or not 0 <= value < 10**60:
                raise ValueError('Score must be a nonnegative integer below 10^60.')
        with self.db:
            row=self.db.execute('SELECT '+','.join(STAT_KEYS)+' FROM scores WHERE user=?',(str(user),)).fetchone()
            if row is None:
                raise ValueError('That player has no recorded scores.')
            before={key:int(value) for key,value in zip(STAT_KEYS,row) if value is not None}
            after=None if category is None else {**before,category:value}
            if category is None:
                self.db.execute('DELETE FROM scores WHERE user=?',(str(user),))
            else:
                self.db.execute('UPDATE scores SET '+category+'=? WHERE user=?',(str(value),str(user)))
            cursor=self.db.execute('''INSERT INTO admin_audit(actor,user,time,action,category,before_values,after_values,reason)
                VALUES(?,?,?,?,?,?,?,?)''',(str(actor),str(user),datetime.now(timezone.utc).isoformat(),
                'remove' if category is None else 'set',category,json.dumps(before),json.dumps(after),reason.strip()))
            self.db.execute('INSERT INTO admin_delivery(audit_id) VALUES(?)',(cursor.lastrowid,))
        return before,after


    def pending_admin_audits(self,limit=20):
        return self.db.execute('''SELECT a.id,a.actor,a.user,a.time,a.action,a.category,
            a.before_values,a.after_values,a.reason FROM admin_audit a
            JOIN admin_delivery d ON d.audit_id=a.id
            WHERE d.delivered_message IS NULL ORDER BY a.id LIMIT ?''',(limit,)).fetchall()

    def mark_admin_delivered(self,audit_id,message_id):
        with self.db:
            self.db.execute('UPDATE admin_delivery SET delivered_message=? WHERE audit_id=?',
                            (str(message_id),audit_id))


    def pending_submission_failures(self,limit=20):
        return self.db.execute('''SELECT id,message,user,url,time,reason FROM submission_failures
            WHERE delivered_message IS NULL ORDER BY id LIMIT ?''',(limit,)).fetchall()

    def mark_failure_delivered(self,failure_id,message_id):
        with self.db:
            self.db.execute('UPDATE submission_failures SET delivered_message=? WHERE id=?',
                            (str(message_id),failure_id))

    def score_values(self,user):
        row=self.db.execute('SELECT '+','.join(STAT_KEYS)+' FROM scores WHERE user=?',(str(user),)).fetchone()
        return {key:int(value) for key,value in zip(STAT_KEYS,row or ()) if value is not None}

    def result(self,message):
        row=self.db.execute('SELECT payload FROM submission_results WHERE message=?',(str(message),)).fetchone()
        return json.loads(row[0]) if row else None
