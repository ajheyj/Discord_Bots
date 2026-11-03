import asyncio
import importlib.util
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
import discord
from ocr import OCRFailure
from store import Store
from audit_channel import AuditChannel
from submission_replay import SubmissionReplay,SubmissionJob,failure_reason

NOW=datetime(2026,11,3,tzinfo=timezone.utc)
def message(mid=1,hours=1):
    return SimpleNamespace(id=mid,created_at=NOW-timedelta(hours=hours),
        guild=SimpleNamespace(id=99),channel=SimpleNamespace(id=123),
        author=SimpleNamespace(id=20,display_name='Player',bot=False),
        attachments=[SimpleNamespace(filename='image.png',size=100,read=AsyncMock(return_value=b'image'))],
        jump_url=f'https://discord.com/channels/99/123/{mid}',reply=AsyncMock())

class ReplayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=str(Path(self.temp.name)/'db')
        self.store=Store(self.path)
        self.bot=SimpleNamespace(reaction=AsyncMock(),fetch_channel=AsyncMock(),wait_until_ready=AsyncMock(),is_closed=lambda:False)
        self.replay=SubmissionReplay(self.bot,self.store,99,123,queue_size=2)
        self.channel=Mock(spec=discord.TextChannel);self.channel.guild=SimpleNamespace(id=99)
        self.bot.fetch_channel.return_value=self.channel
    async def asyncTearDown(self):
        self.store.db.close();self.temp.cleanup()
    def history(self,messages):
        async def iterator():
            for msg in messages:yield msg
        self.channel.history=Mock(side_effect=lambda **kwargs:iterator())
    async def test_scan_includes_failed_and_missing_but_skips_success_and_old(self):
        self.store.record(2,20,'Player','url',error='old failure')
        self.store.record(3,20,'Player','url',dict(packs=1,money=2,coins=3))
        self.history([message(1),message(2),message(3),message(4,73),message(5,-1)])
        self.assertEqual(await self.replay.scan(NOW-timedelta(hours=72),NOW),2)
        ids=[]
        for _ in range(2):
            job=self.replay.queue.get_nowait();ids.append(job.message.id)
            self.assertTrue(job.replay);self.replay.done(job)
        self.assertEqual(ids,[1,2])
        kwargs=self.channel.history.call_args.kwargs
        self.assertIsNone(kwargs['limit']);self.assertTrue(kwargs['oldest_first'])
        self.assertEqual(kwargs['after'],NOW-timedelta(hours=72))
    async def test_duplicate_live_history_and_repeated_scans_are_not_queued_together(self):
        msg=message()
        await self.replay.enqueue(msg)
        self.assertFalse(await self.replay.enqueue(msg,replay=True))
        job=self.replay.queue.get_nowait();self.replay.done(job)
        self.assertTrue(await self.replay.enqueue(msg,replay=True))
        job=self.replay.queue.get_nowait();self.replay.done(job)
        self.assertFalse(await self.replay.enqueue(msg,replay=True))
    async def test_history_waits_for_queue_capacity_instead_of_dropping_images(self):
        self.history([message(1),message(2),message(3)])
        scan=asyncio.create_task(self.replay.scan(NOW-timedelta(hours=72),NOW))
        await asyncio.sleep(0)
        self.assertFalse(scan.done())
        job=await self.replay.queue.get();self.replay.done(job)
        self.assertEqual(await asyncio.wait_for(scan,1),3)
        self.assertEqual(self.replay.queue.qsize(),2)
    async def test_inflight_reservation_prevents_race_during_reaction(self):
        gate=asyncio.Event()
        self.bot.reaction=AsyncMock(side_effect=lambda *args:None)
        async def reaction(*args):await gate.wait()
        self.bot.reaction.side_effect=reaction
        first=asyncio.create_task(self.replay.enqueue(message()))
        await asyncio.sleep(0)
        self.assertFalse(await self.replay.enqueue(message(),replay=True))
        gate.set();self.assertTrue(await first)
        self.assertEqual(self.replay.queue.qsize(),1)
    async def test_only_configured_human_image_posts_are_replayed(self):
        cases=[message(i) for i in range(1,7)]
        cases[0].author.bot=True;cases[1].guild.id=100;cases[2].channel.id=124
        cases[3].attachments=[];cases[4].attachments[0].filename='file.txt'
        cases[5].attachments.append(cases[5].attachments[0])
        for msg in cases:self.assertFalse(await self.replay.enqueue(msg,replay=True))
        self.assertTrue(self.replay.queue.empty())
        for msg in cases:msg.reply.assert_not_awaited()
    async def test_queue_full_live_submission_records_failure_and_clears_hourglass(self):
        await self.replay.enqueue(message(1));await self.replay.enqueue(message(2))
        msg=message(3)
        self.assertFalse(await self.replay.enqueue(msg))
        self.assertNotIn(3,self.replay.inflight)
        self.assertEqual(len(self.store.pending_submission_failures()),1)
        self.bot.reaction.assert_any_await(msg,'⏳',True)
    async def test_scan_rejects_wrong_guild(self):
        self.channel.guild.id=100
        with self.assertRaises(ValueError):await self.replay.scan(NOW-timedelta(hours=72),NOW)
    async def test_disabled_history_does_not_fetch_channel(self):
        self.replay.hours=0;await self.replay.run()
        self.bot.fetch_channel.assert_not_awaited()
    async def test_default_window_and_invalid_settings(self):
        self.assertEqual(SubmissionReplay(self.bot,self.store,99,123).hours,72)
        for value in [-1,721,'72',False]:
            with self.assertRaises(ValueError):SubmissionReplay(self.bot,self.store,99,123,hours=value)

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
        self.assertIn(msg.jump_url,embed.description)
        self.assertIn('Total Money Earned',embed.fields[2].value)
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
        self.assertTrue(any('since processed successfully' in f.value for f in fields))
    async def test_failure_queue_insert_is_atomic_with_failed_audit(self):
        self.store.db.execute("CREATE TRIGGER fail_failure BEFORE INSERT ON submission_failures BEGIN SELECT RAISE(ABORT,'test'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.store.record(1,20,'Player','url',error='unreadable')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM audit').fetchone()[0],0)
    async def test_safe_error_reasons(self):
        self.assertEqual(failure_reason(OCRFailure('Could not confidently read Packs Opened')),'Could not confidently read Packs Opened')
        self.assertIn('timed out',failure_reason(RuntimeError('Tesseract process timeout')))
        self.assertNotIn('secret',failure_reason(ValueError('secret internal details')))
        self.assertIn('Database save failed',failure_reason(sqlite3.OperationalError('path')))

class WorkerTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.module_temp=tempfile.TemporaryDirectory()
        with patch.dict(os.environ,{'GUILD_ID':'99','SUBMISSIONS_CHANNEL_ID':'123','LEADERBOARD_CHANNEL_ID':'789',
            'DATABASE_PATH':str(Path(cls.module_temp.name)/'init.db'),'ADMIN_ROLE_ID':'0','AUDIT_CHANNEL_ID':'0'}):
            spec=importlib.util.spec_from_file_location('test_replay_bot',Path(__file__).resolve().parents[1]/'bot.py')
            cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)
        cls.initial_store=cls.module.DB
    @classmethod
    def tearDownClass(cls):cls.initial_store.db.close();cls.module_temp.cleanup()
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(str(Path(self.temp.name)/'db'))
        self.store_patch=patch.object(self.module,'DB',self.store);self.store_patch.start()
        self.bot=self.module.Bot();self.bot.wait_until_ready=AsyncMock();self.bot.reaction=AsyncMock();self.bot.boards=AsyncMock()
        self.log_patch=patch.object(self.module,'audit_log',SimpleNamespace(flush=AsyncMock()));self.log_patch.start()
    async def asyncTearDown(self):
        await self.bot.close();self.log_patch.stop();self.store_patch.stop();self.store.db.close();self.temp.cleanup()
    async def run_job(self,msg,replay,result=None,error=None):
        await self.bot.submissions.enqueue(msg,replay=replay)
        def extract(_):
            if error:raise error
            return result
        with patch.object(self.module,'extract',side_effect=extract):
            task=asyncio.create_task(self.bot.work())
            try:await asyncio.wait_for(self.bot.queue.join(),3)
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):await task
    async def test_old_failure_reprocessed_successfully_replaces_red_without_double_counting(self):
        msg=message()
        self.store.record(1,20,'Player',msg.jump_url,error='old OCR failure')
        await self.run_job(msg,True,result=dict(packs=5639,money=116*10**18,coins=1478))
        self.assertTrue(self.store.seen(1));self.assertEqual(self.store.ranked('packs')[0][2],5639)
        self.bot.reaction.assert_any_await(msg,'❌',True);self.bot.reaction.assert_any_await(msg,'✅')
        self.bot.reaction.assert_any_await(msg,'⏳',True);msg.reply.assert_not_awaited()
        self.assertFalse(await self.bot.submissions.enqueue(msg,replay=True))
    async def test_replay_failure_is_logged_but_does_not_post_another_public_reply(self):
        msg=message()
        with self.assertLogs(level='ERROR'):await self.run_job(msg,True,error=OCRFailure('Could not confidently read Packs Opened'))
        msg.reply.assert_not_awaited();self.assertFalse(self.store.seen(1))
        self.assertEqual(self.store.pending_submission_failures()[0][-1],'Could not confidently read Packs Opened')
        self.assertFalse(self.bot.submissions.inflight)
    async def test_new_submission_failure_still_receives_original_feedback(self):
        msg=message()
        with self.assertLogs(level='ERROR'):await self.run_job(msg,False,error=OCRFailure('Unreadable image'))
        msg.reply.assert_awaited_once()
        self.assertEqual(len(self.store.pending_submission_failures()),1)

if __name__=='__main__':unittest.main()
