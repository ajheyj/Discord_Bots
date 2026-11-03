import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import discord
from discord import app_commands
from admin_commands import register_admin
from audit_channel import AuditChannel
from store import Store

META={'packs':('Packs',0),'money':('Money',0),'coins':('Coins',0)}

class RoleAuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=str(Path(self.temp.name)/'db')
        self.store=Store(self.path)
        self.store.record(1,20,'Player','url',dict(packs=100,money=200,coins=25))
        self.client=discord.Client(intents=discord.Intents.none())
        self.bot=SimpleNamespace(tree=app_commands.CommandTree(self.client),boards=AsyncMock(),fetch_channel=AsyncMock())
        self.channel=Mock(spec=discord.TextChannel)
        self.channel.guild=SimpleNamespace(id=99)
        self.channel.send=AsyncMock(return_value=SimpleNamespace(id=500))
        self.bot.fetch_channel.return_value=self.channel
        self.audit=AuditChannel(self.bot,self.store,99,123,META,lambda k,v:str(v))
        register_admin(self.bot,self.store,99,META,lambda k,v:str(v),role_id=456,audit_channel=self.audit)
        self.interaction=SimpleNamespace(guild_id=99,permissions=discord.Permissions.none(),user=SimpleNamespace(id=30,roles=[SimpleNamespace(id=456)]),response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock(),is_done=lambda:False),followup=SimpleNamespace(send=AsyncMock()))
    async def asyncTearDown(self):
        self.store.db.close();self.temp.cleanup();await self.client.close()
    async def test_exact_role_required_even_for_administrators(self):
        for name in ('admin-set','admin-remove'):
            command=self.bot.tree.get_command(name)
            self.assertEqual(command.default_permissions.value,0)
            self.assertTrue(await command.checks[0](self.interaction))
            for permissions in [discord.Permissions(manage_guild=True),discord.Permissions(administrator=True)]:
                self.interaction.user.roles=[];self.interaction.permissions=permissions
                with self.assertRaises(app_commands.CheckFailure):await command.checks[0](self.interaction)
            self.interaction.user.roles=[SimpleNamespace(id=456)]
            self.interaction.guild_id=98
            with self.assertRaises(app_commands.CheckFailure):await command.checks[0](self.interaction)
            self.interaction.guild_id=99
            self.interaction.permissions=discord.Permissions.none()
    async def test_set_sends_audit_and_suppresses_mentions(self):
        cmd=self.bot.tree.get_command('admin-set')
        await cmd.callback(self.interaction,SimpleNamespace(id=20),'packs','5','OCR correction @everyone')
        self.assertEqual(self.store.ranked('packs')[0][2],5)
        self.assertEqual(self.store.pending_admin_audits(),[])
        kwargs=self.channel.send.call_args.kwargs
        self.assertFalse(kwargs['allowed_mentions'].everyone)
        self.assertFalse(kwargs['allowed_mentions'].users)
        embed=kwargs['embed'].to_dict()
        self.assertEqual(embed['title'],'Score corrected')
        self.assertIn('Admin audit #',embed['footer']['text'])
        self.assertIn('exact: 100',embed['fields'][2]['value'])
        self.assertIn('exact: 5',embed['fields'][2]['value'])
    async def test_pending_message_survives_restart_and_sends_once_after_success(self):
        self.store.admin_change(30,20,'fix','money',1)
        self.channel.send.side_effect=RuntimeError('offline')
        with self.assertRaises(RuntimeError):await self.audit.flush()
        self.assertEqual(len(self.store.pending_admin_audits()),1)
        self.store.db.close();self.store=Store(self.path)
        self.audit.store=self.store
        self.channel.send.side_effect=None
        await self.audit.flush();await self.audit.flush()
        self.assertEqual(self.store.pending_admin_audits(),[])
        self.assertEqual(self.channel.send.await_count,2) # first failed, second successful
    async def test_wrong_guild_or_nontext_channel_never_receives_audit(self):
        self.store.admin_change(30,20,'fix','coins',1)
        self.channel.guild=SimpleNamespace(id=100)
        with self.assertRaises(ValueError):await self.audit.flush()
        self.channel.send.assert_not_awaited()
        self.bot.fetch_channel.return_value=SimpleNamespace(guild=SimpleNamespace(id=99))
        with self.assertRaises(ValueError):await self.audit.flush()
        self.assertEqual(len(self.store.pending_admin_audits()),1)
    async def test_removed_player_log_contains_all_old_scores(self):
        await self.bot.tree.get_command('admin-remove').callback(self.interaction,SimpleNamespace(id=20),'invalid',True)
        self.assertEqual(self.store.ranked('packs'),[])
        embed=self.channel.send.call_args.kwargs['embed']
        values=[f.value for f in embed.fields]
        self.assertEqual(sum('After: Removed' in v for v in values),3)
    async def test_audit_channel_failure_reports_pending_and_keeps_scores(self):
        self.channel.send.side_effect=RuntimeError('offline')
        with self.assertLogs(level='ERROR'):
            await self.bot.tree.get_command('admin-set').callback(self.interaction,SimpleNamespace(id=20),'coins','0','fix')
        self.assertEqual(self.store.ranked('coins')[0][2],0)
        self.assertEqual(len(self.store.pending_admin_audits()),1)
        self.assertIn('audit channel delivery is pending',self.interaction.followup.send.call_args.args[0])
    async def test_cancel_and_invalid_input_do_not_queue_logs(self):
        await self.bot.tree.get_command('admin-remove').callback(self.interaction,SimpleNamespace(id=20),'invalid',False)
        await self.bot.tree.get_command('admin-set').callback(self.interaction,SimpleNamespace(id=20),'coins','-1','invalid')
        self.assertEqual(self.store.pending_admin_audits(),[])
        self.channel.send.assert_not_awaited()
    async def test_outbox_insert_failure_rolls_back_both_change_and_audit(self):
        self.store.db.execute("CREATE TRIGGER fail_delivery BEFORE INSERT ON admin_delivery BEGIN SELECT RAISE(ABORT,'test'); END")
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):self.store.admin_change(30,20,'fix','packs',0)
        self.assertEqual(self.store.ranked('packs')[0][2],100)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM admin_audit').fetchone()[0],0)
    async def test_migration_keeps_historical_audits_without_reposting(self):
        self.store.admin_change(30,20,'old edit','packs',90)
        self.store.db.execute('DROP TABLE admin_delivery');self.store.db.commit()
        self.store.db.close();self.store=Store(self.path)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM admin_audit').fetchone()[0],1)
        self.assertEqual(self.store.pending_admin_audits(),[])
        self.store.admin_change(30,20,'new edit','packs',80)
        self.assertEqual(len(self.store.pending_admin_audits()),1)

if __name__=='__main__':unittest.main()
