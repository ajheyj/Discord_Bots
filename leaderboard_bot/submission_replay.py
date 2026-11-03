"""Bounded, deduplicated submission queue with a startup history scan."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import discord
import sqlite3
import pytesseract
from ocr import OCRFailure

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')

@dataclass
class SubmissionJob:
    message: object
    replay: bool = False

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
    def __init__(self, bot, store, guild_id, channel_id, hours=72, queue_size=50):
        if type(hours) is not int or not 0 <= hours <= 720:
            raise ValueError('HISTORY_LOOKBACK_HOURS must be an integer from 0 to 720.')
        self.bot, self.store = bot, store
        self.guild_id, self.channel_id, self.hours = guild_id, channel_id, hours
        self.queue = asyncio.Queue(maxsize=queue_size)
        self.inflight = set()
        self.history_enqueued = set()

    def eligible(self, msg):
        return (not msg.author.bot and msg.guild is not None
                and msg.guild.id == self.guild_id and msg.channel.id == self.channel_id
                and bool(msg.attachments))

    async def enqueue(self, msg, replay=False):
        if not self.eligible(msg):
            return False
        if self.store.seen(msg.id):
            if not replay:
                await self.bot.reaction(msg, '✅')
            return False
        if msg.id in self.inflight or (replay and msg.id in self.history_enqueued):
            return False
        if len(msg.attachments) != 1:
            if not replay:
                self.store.record(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,error='Please attach one screenshot per message.')
                await self.bot.reaction(msg, '❌')
                await msg.reply('Please attach one screenshot per message.', mention_author=False)
            return False
        # Backfill only supported images. New uploads retain the worker's validation feedback.
        if replay and not msg.attachments[0].filename.lower().endswith(IMAGE_EXTENSIONS):
            return False
        # Reserve the message ID before any await so live/history events cannot queue it twice.
        self.inflight.add(msg.id)
        queued = False
        try:
            # Set the processing reaction before publishing the job to avoid a late hourglass.
            await self.bot.reaction(msg, '⏳')
            job = SubmissionJob(msg, replay)
            if replay:
                # Wait for capacity instead of losing old images when the queue fills.
                await self.queue.put(job)
            else:
                try:
                    self.queue.put_nowait(job)
                except asyncio.QueueFull:
                    self.store.record(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,error='Processing queue full; retry later or wait for the next startup scan.')
                    await self.bot.reaction(msg, '❌')
                    await msg.reply('The processing queue is full. Please try again later; this image can also be recovered on the next startup scan.', mention_author=False)
                    return False
            queued = True
            if replay:
                self.history_enqueued.add(msg.id)
            return True
        finally:
            if not queued:
                self.inflight.discard(msg.id)
                await self.bot.reaction(msg, '⏳', True)

    def done(self, job):
        self.inflight.discard(job.message.id)
        self.queue.task_done()

    async def scan(self, start, end):
        channel = await self.bot.fetch_channel(self.channel_id)
        if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.guild_id:
            raise ValueError('Submission history requires a text channel in the configured server.')
        scanned = queued = 0
        async for msg in channel.history(limit=None, after=start, before=end, oldest_first=True):
            scanned += 1
            # Check the timestamp ourselves too; the window is based on original posting time.
            if start <= msg.created_at <= end and await self.enqueue(msg, replay=True):
                queued += 1
        logging.info('History scan finished: inspected %s messages, queued %s images; worker continues processing.', scanned, queued)
        return queued

    async def run(self):
        if not self.hours:
            logging.info('Startup submission history scan disabled.')
            return
        await self.bot.wait_until_ready()
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=self.hours)
        logging.info('Scanning submission history from %s to %s (%s hours).', start.isoformat(), end.isoformat(), self.hours)
        while not self.bot.is_closed():
            try:
                await self.scan(start, end)
                return
            except discord.Forbidden:
                logging.exception('Cannot read submission history. Check View Channel and Read Message History; retrying in 60 seconds.')
            except discord.HTTPException:
                logging.exception('Discord history request failed; retrying in 60 seconds.')
            except Exception:
                logging.exception('Startup history scan failed; check configuration and restart after fixing it.')
                return
            await asyncio.sleep(60)
