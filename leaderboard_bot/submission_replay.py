"""Durable admission and optional startup history recovery."""
import asyncio
import logging
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

    async def run(self):
        if not self.hours:return
        await self.bot.wait_until_ready()
        end=datetime.now(timezone.utc);start=end-timedelta(hours=self.hours)
        logging.info('Scanning submission history from %s to %s (%s hours).',start.isoformat(),end.isoformat(),self.hours)
        while not self.bot.is_closed():
            try:
                await self.scan(start,end)
                await self.scan_dms(start,end)
                return
            except (discord.Forbidden,discord.HTTPException):
                logging.exception('History request failed; check View Channel/Read Message History. Retrying in 60 seconds.')
                await asyncio.sleep(60)
            except Exception:
                logging.exception('History scan failed; inspect configuration and restart after fixing it.')
                return
