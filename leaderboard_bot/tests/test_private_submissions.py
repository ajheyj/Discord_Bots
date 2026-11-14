import asyncio
import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
import discord
from discord import app_commands
from store import Store
from ocr import resolve,merge_screenshots,OCRFailure
from collections import defaultdict
from dm_submissions import register_submissions
from submission_results import result_embed
from submission_replay import SubmissionReplay
from test_durable_queue import config,message,bot_and_channel
from audit_channel import AuditChannel

class PartialTests(unittest.TestCase):
    def test_one_confident_stat_is_enough_and_conflicts_are_omitted(self):
        got=resolve(defaultdict(list,packs=[100,100],money=[5,6],coins=[8]))
        self.assertEqual(got['packs'],100);self.assertNotIn('money',got);self.assertNotIn('coins',got)
        self.assertEqual(len(got['_warnings']),2)
    def test_no_confident_stat_still_fails(self):
        with self.assertRaises(OCRFailure):resolve(defaultdict(list))
    def test_missing_name_does_not_prevent_discord_keyed_merge(self):
        self.assertEqual(merge_screenshots([dict(packs=2),dict(username='A',shiny=4)]),dict(username='A',packs=2,shiny=4))
    def test_runner_preserves_good_image_when_other_image_fails(self):
        import ocr_runner
        with tempfile.TemporaryDirectory() as temp:
            a=Path(temp)/'a';b=Path(temp)/'b';a.write_bytes(b'a');b.write_bytes(b'b')
            out=io.StringIO()
            with patch.object(ocr_runner,'extract',side_effect=[OCRFailure('Unreadable image'),dict(packs=12)]),contextlib.redirect_stdout(out):ocr_runner.main([a,b])
            result=json.loads(out.getvalue());self.assertTrue(result['ok']);self.assertEqual(result['values']['packs'],12)
            self.assertIn('Image 1',result['values']['_warnings'][0])

class PrivateFlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.store=Store(self.root/'db')
        self.messages={1:message()};self.bot,self.channel=bot_and_channel(self.messages)
        self.bot.fetch_user=AsyncMock(return_value=SimpleNamespace(send=AsyncMock()))
        self.replay=SubmissionReplay(self.bot,self.store,99,123,config=config(self.root))
        self.client=discord.Client(intents=discord.Intents.none());self.bot.tree=app_commands.CommandTree(self.client)
        register_submissions(self.bot,self.store,99)
        self.user=SimpleNamespace(id=20,send=AsyncMock())
        self.interaction=SimpleNamespace(guild_id=99,user=self.user,
            response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock()),followup=SimpleNamespace(send=AsyncMock()))
    async def asyncTearDown(self):
        await self.replay.pipeline.close();await self.client.close();self.store.db.close();self.tmp.cleanup()
    async def open_session(self):await self.bot.tree.get_command('submit').callback(self.interaction)
    async def test_submit_is_private_and_persists_session(self):
        await self.open_session();self.user.send.assert_awaited_once()
        self.assertTrue(self.interaction.response.defer.call_args.kwargs['ephemeral'])
        self.assertTrue(self.interaction.followup.send.call_args.kwargs['ephemeral'])
        self.assertGreater(self.store.db.execute('SELECT expires FROM dm_sessions').fetchone()[0],time.time())
        dm=message();dm.guild=None;self.assertTrue(self.replay.eligible(dm))
    async def test_blocked_dm_does_not_open_session(self):
        self.user.send.side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='blocked'),'blocked')
        await self.open_session();self.assertEqual(self.store.db.execute('SELECT count(*) FROM dm_sessions').fetchone()[0],0)
        self.assertIn('Allow direct messages',self.interaction.followup.send.call_args.args[0])
    async def test_wrong_server_cannot_open_session(self):
        self.interaction.guild_id=100;await self.open_session();self.user.send.assert_not_awaited()
        self.assertTrue(self.interaction.response.send_message.call_args.kwargs['ephemeral'])
    async def test_expired_or_unopened_dm_session_is_not_accepted(self):
        dm=message();dm.guild=None;self.assertFalse(self.replay.eligible(dm))
        self.store.db.execute('INSERT INTO dm_sessions VALUES(20,?)',(time.time()-1,));self.store.db.commit()
        self.assertFalse(self.replay.eligible(dm))
    async def test_dm_download_uses_saved_dm_channel_after_restart(self):
        await self.open_session();dm=self.messages[1];dm.guild=None;dm.channel.id=888
        self.assertTrue(await self.replay.enqueue(dm))
        row=self.replay.jobs.claim('download');self.assertEqual(row['source_channel'],'888')
        await self.replay.pipeline.download(row)
        self.bot.fetch_channel.assert_awaited_with(888);self.assertTrue(self.replay.pipeline.spool.complete(row))
        dm.reply.assert_not_awaited();self.bot.reaction.assert_not_awaited()
    async def test_partial_result_preserves_bests_and_persists_exact_changes(self):
        self.store.record(9,20,'Old','url',dict(packs=100,money=1000,coins=20,playtime=3600,username='Old'),submitted_at=self.messages[1].created_at-timedelta(days=1))
        msg=self.messages[1];self.replay.pipeline.admit(msg)
        self.replay.jobs.succeed(1,dict(packs=110,coins=10,shiny=8,username='New',_warnings=['money unclear']))
        result=self.store.result(1)
        self.assertEqual(result['before']['packs'],100);self.assertEqual(result['after']['packs'],110)
        self.assertEqual(result['after']['money'],1000);self.assertEqual(result['after']['coins'],20)
        self.assertEqual(result['after']['playtime'],3600);self.assertEqual(self.store.identity(20),'New')
        await self.replay.pipeline.notify(self.replay.jobs.get(1));await self.replay.pipeline.notify(self.replay.jobs.get(1))
        self.bot.fetch_user.return_value.send.assert_awaited_once()
        embed=self.bot.fetch_user.return_value.send.call_args.kwargs['embed']
        self.assertTrue(any('100 → **110**' in field.value for field in embed.fields))
        msg.reply.assert_not_awaited();msg.add_reaction.assert_not_awaited()
    async def test_result_command_only_reads_requesting_users_result(self):
        self.store.record(1,20,'A','url',dict(packs=5));self.store.record(2,30,'B','url',dict(packs=999))
        await self.bot.tree.get_command('submission-result').callback(self.interaction)
        kwargs=self.interaction.response.send_message.call_args.kwargs
        self.assertTrue(kwargs['ephemeral']);self.assertNotIn('999',str(kwargs['embed'].to_dict()))
    async def test_dm_block_is_terminal_and_private_result_survives(self):
        self.replay.pipeline.admit(self.messages[1]);self.replay.jobs.succeed(1,dict(packs=5))
        self.bot.fetch_user.return_value.send.side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='blocked'),'blocked')
        await self.replay.pipeline.notify(self.replay.jobs.get(1))
        self.assertEqual(self.replay.jobs.notifications(),[]);self.assertEqual(self.store.result(1)['recognized'],dict(packs=5))
    async def test_audit_copies_cached_dm_image_and_matches_result(self):
        self.bot.audit_channel_id=456;self.replay.pipeline.audit_enabled=True;self.bot.config=self.replay.pipeline.config
        await self.open_session();msg=self.messages[1];msg.guild=None
        await self.replay.enqueue(msg);row=self.replay.jobs.claim('download');await self.replay.pipeline.download(row)
        row=self.replay.jobs.claim('ocr')
        with patch('durable_service.run_ocr',new=AsyncMock(return_value=dict(packs=15))):await self.replay.pipeline.process_ocr(row)
        self.assertTrue(self.replay.pipeline.spool.complete(row))
        channel=Mock(spec=discord.TextChannel);channel.guild=SimpleNamespace(id=99,filesize_limit=1000000)
        channel.send=AsyncMock(return_value=SimpleNamespace(id=777));self.bot.fetch_channel.return_value=channel
        audit=AuditChannel(self.bot,self.store,99,456,{},str);await audit.flush()
        self.assertEqual(len(channel.send.call_args.kwargs['files']),2)
        self.assertIn('Screenshot results',channel.send.call_args.kwargs['embed'].title)
        self.replay.pipeline.cleanup();self.assertFalse(self.replay.pipeline.spool.directory(1).exists())
    async def test_startup_dm_scan_recovers_missed_images_from_open_session(self):
        await self.open_session();msg=self.messages[1];msg.guild=None;msg.channel.id=888
        async def history(**kwargs):yield msg
        dm=SimpleNamespace(history=history)
        self.bot.fetch_user.return_value.create_dm=AsyncMock(return_value=dm)
        await self.replay.scan_dms(msg.created_at-timedelta(hours=1),msg.created_at+timedelta(hours=1))
        self.assertEqual(self.replay.jobs.get(1)['source_channel'],'888')
        self.assertEqual(self.replay.jobs.counts(),{'download_wait':1})
    async def test_expired_session_replays_only_messages_posted_before_expiry(self):
        msg=self.messages[1];msg.guild=None
        with self.store.db:self.store.db.execute('INSERT INTO dm_sessions VALUES(?,?)',('20',msg.created_at.timestamp()+1))
        self.assertFalse(self.replay.eligible(msg))
        self.assertTrue(self.replay.eligible(msg,replay=True))
        msg.created_at+=timedelta(seconds=2)
        self.assertFalse(self.replay.eligible(msg,replay=True))
    async def test_transient_dm_error_keeps_notification_pending_without_undoing_score(self):
        self.replay.pipeline.admit(self.messages[1]);self.replay.jobs.succeed(1,dict(shiny=8))
        self.bot.fetch_user.return_value.send.side_effect=discord.HTTPException(SimpleNamespace(status=503,reason='offline'),'offline')
        with self.assertRaises(discord.HTTPException):await self.replay.pipeline.notify(self.replay.jobs.get(1))
        self.assertTrue(self.store.seen(1));self.assertEqual(len(self.replay.jobs.notifications()),1)
        self.bot.fetch_user.return_value.send.side_effect=None
        await self.replay.pipeline.notify(self.replay.jobs.get(1));self.assertEqual(self.replay.jobs.notifications(),[])
