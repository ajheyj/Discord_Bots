import asyncio
import tempfile
import unittest
import sqlite3
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock
import discord
from ocr import OCRFailure
from store import Store
from audit_channel import AuditChannel
from submission_replay import SubmissionReplay,failure_reason
from queue_config import QueueConfig

NOW=datetime(2026,11,10,tzinfo=timezone.utc)
def message(mid=1,hours=1):
    return SimpleNamespace(id=mid,created_at=NOW-timedelta(hours=hours),
        guild=SimpleNamespace(id=99),channel=SimpleNamespace(id=123),
        author=SimpleNamespace(id=20,display_name='Player',bot=False,send=AsyncMock()),
        attachments=[SimpleNamespace(id=mid*10,filename='image.png',size=100,read=AsyncMock(return_value=b'image'))],
        jump_url=f'https://discord.com/channels/99/123/{mid}',reply=AsyncMock())

class ReplayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.store=Store(root/'db')
        cfg=QueueConfig(root/'spool',root/'backups',backup_hours=0,min_free_bytes=0)
        self.bot=SimpleNamespace(reaction=AsyncMock(),fetch_channel=AsyncMock(),wait_until_ready=AsyncMock(),is_closed=lambda:False,mark_scores_changed=Mock())
        self.replay=SubmissionReplay(self.bot,self.store,99,123,config=cfg)
        self.channel=Mock(spec=discord.TextChannel);self.channel.guild=SimpleNamespace(id=99)
        self.bot.fetch_channel.return_value=self.channel
    async def asyncTearDown(self):
        await self.replay.pipeline.close();self.store.db.close();self.temp.cleanup()
    def history(self,messages):
        async def iterator():
            for msg in messages:yield msg
        self.channel.history=Mock(side_effect=lambda **kwargs:iterator())
    async def test_scan_includes_failed_missing_but_skips_success_old_and_future(self):
        self.store.record(2,20,'Player','url',error='old failure')
        self.store.record(3,20,'Player','url',dict(packs=1,money=2,coins=3))
        self.history([message(1),message(2),message(3),message(4,73),message(5,-1)])
        self.assertEqual(await self.replay.scan(NOW-timedelta(hours=72),NOW),2)
        ids=self.replay.jobs.db.execute('SELECT message FROM queue_jobs ORDER BY message').fetchall()
        self.assertEqual(ids,[('1',),('2',)])
        kwargs=self.channel.history.call_args.kwargs
        self.assertIsNone(kwargs['limit']);self.assertTrue(kwargs['oldest_first'])
        self.assertEqual(kwargs['after'],NOW-timedelta(hours=72))
    async def test_duplicate_live_history_and_restart_use_saved_job(self):
        msg=message();self.assertTrue(await self.replay.enqueue(msg))
        self.assertFalse(await self.replay.enqueue(msg,replay=True))
        other=SubmissionReplay(self.bot,self.store,99,123,config=self.replay.pipeline.config)
        self.assertFalse(await other.enqueue(msg,replay=True))
        self.assertEqual(self.replay.jobs.counts(),{'download_wait':1})
        msg.attachments[0].read.assert_not_awaited()
    async def test_only_configured_human_image_posts_are_replayed(self):
        cases=[message(i) for i in range(1,7)]
        cases[0].author.bot=True;cases[1].guild.id=100;cases[2].channel.id=124
        cases[3].attachments=[];cases[4].attachments[0].filename='file.txt'
        cases[5].attachments.extend([cases[5].attachments[0],cases[5].attachments[0]])
        for msg in cases:self.assertFalse(await self.replay.enqueue(msg,replay=True))
        self.assertEqual(self.replay.jobs.counts(),{})
        for msg in cases:msg.reply.assert_not_awaited()
    async def test_full_queue_rejects_live_submission_explicitly(self):
        self.replay.pipeline.config.max_jobs=1
        self.assertTrue(await self.replay.enqueue(message(1)))
        msg=message(2);self.assertFalse(await self.replay.enqueue(msg))
        self.assertIsNone(self.replay.jobs.get(2));msg.reply.assert_not_awaited();msg.author.send.assert_awaited_once()
        self.assertEqual(len(self.store.pending_submission_failures()),1)
    async def test_disabled_scan_and_invalid_settings(self):
        self.assertEqual(self.replay.hours,72);self.replay.hours=0
        await self.replay.run();self.bot.fetch_channel.assert_not_awaited()
        for hours in [-1,721,'72',False]:
            with self.assertRaises(ValueError):SubmissionReplay(self.bot,self.store,99,123,hours=hours)
    async def test_wrong_server_channel_is_rejected(self):
        self.channel.guild.id=100
        with self.assertRaises(ValueError):await self.replay.scan(NOW-timedelta(hours=72),NOW)

class FailureLogTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=str(Path(self.temp.name)/'db');self.store=Store(self.path)
        self.channel=Mock(spec=discord.TextChannel);self.channel.guild=SimpleNamespace(id=99)
        self.channel.send=AsyncMock(return_value=SimpleNamespace(id=700))
        self.bot=SimpleNamespace(fetch_channel=AsyncMock(return_value=self.channel))
        self.audit=AuditChannel(self.bot,self.store,99,456,{'packs':('Packs',0),'money':('Money',0),'coins':('Coins',0)},lambda k,v:str(v))
    async def asyncTearDown(self):self.store.db.close();self.temp.cleanup()
    async def test_failure_embed_has_original_link_player_and_reason_without_pings(self):
        msg=message()
        self.store.record(msg.id,20,'Player',msg.jump_url,error='Could not confidently read Total Money Earned')
        await self.audit.flush()
        embed=self.channel.send.call_args.kwargs['embed']
        self.assertTrue(any(msg.jump_url in f.value for f in embed.fields))
        self.assertIn('Total Money Earned',embed.description)
        mentions=self.channel.send.call_args.kwargs['allowed_mentions']
        self.assertFalse(mentions.everyone);self.assertFalse(mentions.users)
        self.assertEqual(self.store.pending_submission_failures(),[])
    async def test_same_message_reason_delivered_once_even_after_restart(self):
        msg=message()
        self.store.record(1,20,'Player',msg.jump_url,error='unreadable');await self.audit.flush()
        self.store.db.close();self.store=Store(self.path);self.audit.store=self.store
        self.store.record(1,20,'Player',msg.jump_url,error='unreadable');await self.audit.flush()
        self.assertEqual(self.channel.send.await_count,1)
        self.store.record(1,20,'Player',msg.jump_url,error='different reason');await self.audit.flush()
        self.assertEqual(self.channel.send.await_count,2)
    async def test_discord_outage_preserves_pending_failure_report(self):
        self.store.record(1,20,'Player','url',error='unreadable')
        self.channel.send.side_effect=RuntimeError('offline')
        with self.assertRaises(RuntimeError):await self.audit.flush()
        self.assertEqual(len(self.store.pending_submission_failures()),1)
        self.channel.send.side_effect=None;await self.audit.flush()
        self.assertEqual(self.store.pending_submission_failures(),[])
    async def test_success_after_failure_is_labeled_as_recovered(self):
        self.store.record(1,20,'Player','url',error='unreadable')
        self.store.record(1,20,'Player','url',dict(packs=1,money=2,coins=3))
        await self.audit.flush()
        fields=self.channel.send.call_args.kwargs['embed'].fields
        self.assertTrue(any('→' in f.value for f in fields))
    async def test_failure_queue_insert_is_atomic_with_failed_audit(self):
        self.store.db.execute("CREATE TRIGGER fail_failure BEFORE INSERT ON submission_failures BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.store.record(1,20,'Player','url',error='unreadable')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM audit').fetchone()[0],0)
    async def test_safe_error_reasons(self):
        self.assertEqual(failure_reason(OCRFailure('Could not confidently read Packs Opened')),'Could not confidently read Packs Opened')
        self.assertIn('timed out',failure_reason(RuntimeError('Tesseract process timeout')))
        self.assertNotIn('secret',failure_reason(ValueError('secret internal details')))
        self.assertIn('Database save failed',failure_reason(sqlite3.OperationalError('path')))


if __name__=='__main__':unittest.main()
