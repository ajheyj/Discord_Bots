import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock
import discord
from store import Store
from audit_channel import AuditChannel

class ThreadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'db')
        self.threads={}
        def make(mid):
            t=Mock(spec=discord.Thread);t.id=mid;t.parent_id=456;t.guild=SimpleNamespace(id=99)
            t.name={10:'Complete reads',20:'Failed reads',30:'Partial reads'}[mid];t.archived=False;t.send=AsyncMock(return_value=SimpleNamespace(id=mid+100));t.edit=AsyncMock()
            self.threads[mid]=t;return t
        self.success=make(10);self.failed=make(20);self.partial=make(30)
        self.channel=Mock(spec=discord.TextChannel);self.channel.id=456
        self.channel.guild=SimpleNamespace(id=99,filesize_limit=1000000)
        self.channel.create_thread=AsyncMock(side_effect=[self.success,self.failed,self.partial])
        self.channel.send=AsyncMock()
        async def fetch(mid):return self.channel if mid==456 else self.threads[mid]
        self.bot=SimpleNamespace(fetch_channel=AsyncMock(side_effect=fetch))
        self.audit=AuditChannel(self.bot,self.store,99,456,{},str)
    async def asyncTearDown(self):self.store.db.close();self.tmp.cleanup()
    async def test_create_reuse_and_unarchive(self):
        self.assertEqual(await self.audit.submission_thread(self.channel,'successful'),self.success)
        self.success.archived=True
        self.assertEqual(await self.audit.submission_thread(self.channel,'successful'),self.success)
        self.success.edit.assert_awaited_once_with(archived=False)
        self.channel.create_thread.assert_awaited_once()
    async def test_success_failure_and_partial_routing(self):
        self.store.record(1,7,'P','url',{'packs':1,'money':2,'coins':3,'shiny':4})
        self.store.record(2,7,'P','url',error='unreadable')
        self.store.record(3,7,'P','url',{'packs':2,'_warnings':['money unclear']})
        await self.audit.flush()
        self.assertEqual(self.success.send.await_count,1)
        self.assertEqual(self.failed.send.await_count,1)
        self.partial.send.assert_awaited_once()
        self.channel.send.assert_not_awaited()
        await self.audit.flush()
        self.assertEqual(self.failed.send.await_count,1)
    async def test_permission_failure_keeps_result_pending(self):
        self.store.record(1,7,'P','url',{'packs':1})
        self.channel.create_thread.side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='denied'),'denied')
        with self.assertRaises(discord.Forbidden):await self.audit.flush()
        self.assertIsNone(self.store.db.execute('SELECT delivered_message FROM submission_results').fetchone()[0])
    async def test_wrong_parent_is_rejected(self):
        await self.audit.submission_thread(self.channel,'successful')
        self.success.parent_id=987
        with self.assertRaises(ValueError):await self.audit.submission_thread(self.channel,'successful')

    async def test_missing_core_field_is_partial_but_absent_playtime_is_complete(self):
        self.assertEqual(self.audit.read_status({'recognized':{'packs':0}}),'partial')
        self.assertEqual(self.audit.read_status({'recognized':dict(packs=0,money=0,coins=0,shiny=0)}),'successful')
        self.assertEqual(self.audit.read_status({'recognized':{}}),'failed')
    async def test_existing_threads_are_renamed_without_moving_posts(self):
        await self.audit.submission_thread(self.channel,'successful')
        self.success.name='Successful submissions'
        await self.audit.submission_thread(self.channel,'successful')
        self.success.edit.assert_awaited_once_with(name='Complete reads')
        self.channel.create_thread.assert_awaited_once()
