"""Durable admission and optional startup history recovery."""
import asyncio
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone
import discord
import sqlite3
import pytesseract
from ocr import OCRFailure

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')

def failure_reason(error):
    """Actionable reasons for moderators; raw exceptions stay in service logs."""
    if isinstance(error, OCRFailure):
        return str(error)[:500]
    if isinstance(error, pytesseract.TesseractNotFoundError):
        return 'OCR engine unavailable: check the Tesseract installation and TESSERACT_CMD.'
    if isinstance(error, RuntimeError) and 'timeout' in str(error).lower():
        return 'OCR timed out while reading the image.'
    if isinstance(error, discord.NotFound):
        return 'Original message or attachment is no longer available.'
    if isinstance(error, discord.Forbidden):
        return 'Discord denied access to the message or attachment.'
    if isinstance(error, discord.HTTPException):
        return 'Discord could not download the attachment; this may be temporary.'
    if isinstance(error, sqlite3.Error):
        return 'Database save failed; inspect the service logs and database permissions.'
    return 'Unexpected processing error; inspect the service logs for details.'

class SubmissionReplay:
    def __init__(self,bot,store,guild_id,channel_id,hours=72,config=None):
        from queue_config import QueueConfig
        from durable_service import DurablePipeline
        if type(hours) is not int or not 0<=hours<=720:
            raise ValueError('HISTORY_LOOKBACK_HOURS must be an integer from 0 to 720.')
        self.bot,self.store,self.guild_id,self.channel_id,self.hours=bot,store,guild_id,channel_id,hours
        self.pipeline=DurablePipeline(bot,store,guild_id,channel_id,config or QueueConfig.from_env(store.path))
        self.jobs=self.pipeline.jobs
        self.history_enqueued=set()
        # A reader change permits one new automatic review, not every restart.
        root=Path(__file__).parent
        digest=hashlib.sha256()
        for name in ('ocr.py','player_panel.py','image_scan.py','durable_service.py','durable_jobs.py'):
            path=root/name
            if path.exists():digest.update(path.read_bytes())
        self.reader_revision=digest.hexdigest()
        self.store.db.execute("CREATE TABLE IF NOT EXISTS automatic_reviews(message TEXT,revision TEXT,PRIMARY KEY(message,revision))")
        self.store.db.commit()

    def eligible(self,msg,replay=False):
        if msg.author.bot or not msg.attachments:return False
        if msg.guild is None:
            import time
            session=self.store.db.execute('SELECT expires FROM dm_sessions WHERE user=?',(str(msg.author.id),)).fetchone()
            return bool(session and session[0]>(msg.created_at.timestamp() if replay else time.time()))
        return msg.guild.id==self.guild_id and msg.channel.id==self.channel_id

    async def enqueue(self,msg,replay=False):
        from durable_jobs import QueueRejected
        if not self.eligible(msg,replay):return False
        if self.store.seen(msg.id):return False
        if replay and msg.id in self.history_enqueued:return False
        failed=self.jobs.get(msg.id)
        reviewing=bool(replay and failed and failed['state']=='failed')
        if reviewing and self.store.db.execute('SELECT 1 FROM automatic_reviews WHERE message=? AND revision=?',
                (str(msg.id),self.reader_revision)).fetchone():return False
        try:
            accepted=self.pipeline.admit(msg,replay)
        except QueueRejected as error:
            if replay:
                logging.warning('History submission %s was not accepted: %s',msg.id,error)
            else:
                self.store.record(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,error=str(error))
                await self.private_notice(msg,str(error),result=True)
            return False
        except Exception:
            logging.exception('Submission could not be safely queued: %s',msg.id)
            self.pipeline.last_error='Database/storage admission failed; inspect service logs.'
            if not replay:
                self.store.record(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,error='Could not save this submission to the queue. Please try again later.')
                await self.private_notice(msg,'Could not save this submission to the queue. Please try again later.',result=True)
            return False
        if accepted:
            if reviewing:
                with self.store.db:self.store.db.execute('INSERT OR IGNORE INTO automatic_reviews VALUES(?,?)',
                    (str(msg.id),self.reader_revision))
            if replay:self.history_enqueued.add(msg.id)
            # Acknowledgment follows the committed queue row, never precedes it.
            if not replay:await self.private_notice(msg,'Your screenshot submission is saved in the queue. I will DM you the results.')
        return accepted

    async def private_notice(self,msg,text,result=False):
        status=None
        try:
            await msg.author.send(text,allowed_mentions=discord.AllowedMentions.none());status='sent'
        except discord.Forbidden:
            status='blocked';logging.info('DM blocked for submission %s; private /submission-result is available.',msg.id)
        except discord.HTTPException:logging.warning('Private notice could not be delivered for %s.',msg.id)
        if result and status:
            with self.store.db:self.store.db.execute('UPDATE submission_results SET dm_status=? WHERE message=?',(status,str(msg.id)))

    async def scan(self,start,end):
        channel=await self.pipeline.source_channel()
        scanned=queued=0
        async for msg in channel.history(limit=None,after=start,before=end,oldest_first=True):
            scanned+=1
            if start<=msg.created_at<=end and await self.enqueue(msg,replay=True):queued+=1
        logging.info('History scan finished: inspected %s messages, queued %s images; durable workers continue processing.',scanned,queued)
        return queued

    async def scan_dms(self,start,end):
        # Accepted DM jobs already resume from SQLite; discover missed posts while the bot was offline.
        sessions=self.store.db.execute('SELECT user,expires FROM dm_sessions WHERE expires>=?',(start.timestamp(),)).fetchall()
        for user,expires in sessions:
            try:
                member=await self.bot.fetch_user(int(user))
                channel=await member.create_dm()
                async for msg in channel.history(limit=None,after=start,before=end,oldest_first=True):
                    if msg.author.id==int(user) and start<=msg.created_at<=end and msg.created_at.timestamp()<=expires:
                        await self.enqueue(msg,replay=True)
            except (discord.Forbidden,discord.NotFound):
                logging.warning('DM history unavailable for a screenshot session.')

    async def review_failed_dms(self,start,end):
        """Fetch original DM messages even after their upload session expires."""
        rows=self.jobs.rows("SELECT * FROM queue_jobs WHERE state='failed' AND source_channel IS NOT NULL ORDER BY added")
        for row in rows:
            created=datetime.fromisoformat(row['created_at'])
            if not start<=created<=end:continue
            if self.store.db.execute('SELECT 1 FROM automatic_reviews WHERE message=? AND revision=?',
                    (row['message'],self.reader_revision)).fetchone():continue
            try:
                user=await self.bot.fetch_user(int(row['user']))
                channel=await user.create_dm()
                if str(channel.id)!=row['source_channel']:continue
                msg=await channel.fetch_message(int(row['message']))
                if str(msg.author.id)!=row['user'] or msg.guild is not None:continue
                # Saved accepted identity authorizes recovery; no new upload session needed.
                if self.pipeline.admit(msg,replay=True):
                    with self.store.db:self.store.db.execute('INSERT OR IGNORE INTO automatic_reviews VALUES(?,?)',
                        (row['message'],self.reader_revision))
                    self.history_enqueued.add(msg.id)
            except (discord.NotFound,discord.Forbidden):
                logging.warning('Original failed DM submission %s is unavailable.',row['message'])
            except Exception:
                logging.exception('Automatic review could not queue submission %s; continuing.',row['message'])

    async def run(self):
        if not self.hours:return
        await self.bot.wait_until_ready()
        end=datetime.now(timezone.utc);start=end-timedelta(hours=self.hours)
        logging.info('Scanning submission history from %s to %s (%s hours).',start.isoformat(),end.isoformat(),self.hours)
        while not self.bot.is_closed():
            try:
                await self.review_failed_dms(start,end)
                await self.scan(start,end)
                await self.scan_dms(start,end)
                return
            except (discord.Forbidden,discord.HTTPException):
                logging.exception('History request failed; check View Channel/Read Message History. Retrying in 60 seconds.')
                await asyncio.sleep(60)
            except Exception:
                logging.exception('History scan failed; inspect configuration and restart after fixing it.')
                return
