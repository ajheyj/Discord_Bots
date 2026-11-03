import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import discord
from discord import app_commands
from admin_commands import parse_score, register_admin
from store import Store

class AdminStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name)/'scores.db')
        self.store = Store(self.path)
        self.store.record(10, 20, 'Player', 'url', dict(packs=100, money=10**18+1, coins=25))
    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()
    def test_lower_one_category_and_preserve_other_data(self):
        self.store.save_board('packs', 500)
        before, after = self.store.admin_change(30, 20, 'OCR correction', 'packs', 4)
        self.assertEqual(before['packs'], 100)
        self.assertEqual(after, dict(packs=4, money=10**18+1, coins=25))
        self.assertEqual(self.store.ranked('packs')[0][2], 4)
        self.assertTrue(self.store.seen(10))
        self.assertEqual(self.store.board('packs'), 500)
        audit = self.store.db.execute('SELECT actor,user,action,before_values,after_values,reason FROM admin_audit').fetchone()
        self.assertEqual(audit[:3], ('30', '20', 'set'))
        self.assertEqual(json.loads(audit[3]), before)
        self.assertEqual(json.loads(audit[4]), after)
        self.assertEqual(audit[5], 'OCR correction')
    def test_remove_persists_audit_and_allows_future_submission(self):
        self.store.admin_change(30, 20, 'Invalid entry')
        for category in ('packs','money','coins'):
            self.assertEqual(self.store.ranked(category), [])
        audit = self.store.db.execute('SELECT action,after_values FROM admin_audit').fetchone()
        self.assertEqual(audit, ('remove','null'))
        self.store.record(11, 20, 'Player', 'url', dict(packs=2,money=3,coins=4))
        self.assertEqual(self.store.ranked('packs')[0][2], 2)
    def test_audit_failure_rolls_back_score_change(self):
        self.store.db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON admin_audit BEGIN SELECT RAISE(ABORT,'test'); END")
        for category, value in [('packs',1), (None,None)]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.admin_change(30,20,'reason',category,value)
            self.assertEqual(self.store.ranked('packs')[0][2],100)
    def test_invalid_edits_have_no_effect(self):
        cases=[(20,'', 'packs',1),(999,'reason','packs',1),(20,'reason','bad',1),(20,'reason','packs',-1)]
        for user,reason,category,value in cases:
            with self.assertRaises(ValueError): self.store.admin_change(30,user,reason,category,value)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM admin_audit').fetchone()[0],0)
        self.assertEqual(self.store.ranked('packs')[0][2],100)
    def test_migration_and_reopen(self):
        self.store.db.execute('DROP TABLE admin_audit')
        self.store.db.close()
        self.store=Store(self.path)
        self.store.admin_change(30,20,'fix','money',10**18+2)
        self.store.db.close();self.store=Store(self.path)
        self.assertEqual(self.store.ranked('money')[0][2],10**18+2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM admin_audit').fetchone()[0],1)
    def test_parse_exact_and_reject_malformed(self):
        self.assertEqual(parse_score('money','$1.93Qi'),1930000000000000000)
        self.assertEqual(parse_score('money','12345678901234567890123456789012345'),12345678901234567890123456789012345)
        self.assertEqual(parse_score('coins','1,234'),1234)
        self.assertEqual(parse_score('packs','0'),0)
        for category, value in [('packs','1.5'),('coins','2K'),('money','1,2'),('money','1e9'),('money','1QiOops'),('money','-1'),('money','0.5'),('money','9'*61),('packs','$2')]:
            with self.assertRaises(ValueError):parse_score(category,value)

class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.store=Store(str(Path(self.temp.name)/'db'))
        self.store.record(10,20,'Player','url',dict(packs=100,money=200,coins=25))
        self.client=discord.Client(intents=discord.Intents.none())
        self.bot=SimpleNamespace(tree=app_commands.CommandTree(self.client),boards=AsyncMock())
        register_admin(self.bot,self.store,99,{'packs':('Packs',0),'money':('Money',0),'coins':('Coins',0)},lambda k,v:str(v))
        self.interaction=SimpleNamespace(guild_id=99,permissions=discord.Permissions(manage_guild=True),user=SimpleNamespace(id=30),response=SimpleNamespace(defer=AsyncMock(),send_message=AsyncMock(),is_done=lambda:False),followup=SimpleNamespace(send=AsyncMock()))
    async def asyncTearDown(self):
        self.store.db.close();self.temp.cleanup();await self.client.close()
    async def test_checks_deny_non_admin_and_other_server(self):
        for name in ('admin-set','admin-remove'):
            cmd=self.bot.tree.get_command(name)
            self.assertTrue(cmd.default_permissions.manage_guild)
            self.assertTrue(cmd.guild_only)
            self.interaction.permissions=discord.Permissions.none()
            with self.assertRaises(app_commands.MissingPermissions):await cmd.checks[0](self.interaction)
            self.interaction.permissions=discord.Permissions(manage_guild=True)
            self.interaction.guild_id=100
            with self.assertRaises(app_commands.CheckFailure):await cmd.checks[0](self.interaction)
            self.interaction.guild_id=99
            self.assertTrue(await cmd.checks[0](self.interaction))
        self.assertEqual(self.store.ranked('packs')[0][2],100)
    async def test_set_refreshes_and_replies_privately(self):
        cmd=self.bot.tree.get_command('admin-set')
        await cmd.callback(self.interaction,SimpleNamespace(id=20),'packs','5','OCR error')
        self.assertEqual(self.store.ranked('packs')[0][2],5)
        self.bot.boards.assert_awaited_once()
        self.assertTrue(self.interaction.followup.send.call_args.kwargs['ephemeral'])
    async def test_cancel_and_confirm_removal(self):
        cmd=self.bot.tree.get_command('admin-remove')
        await cmd.callback(self.interaction,SimpleNamespace(id=20),'reason',False)
        self.assertEqual(len(self.store.ranked('packs')),1)
        self.bot.boards.assert_not_awaited()
        await cmd.callback(self.interaction,SimpleNamespace(id=20),'reason',True)
        self.assertEqual(self.store.ranked('packs'),[])
        self.bot.boards.assert_awaited_once()
    async def test_display_failure_does_not_undo_save(self):
        self.bot.boards.side_effect=RuntimeError('Discord unavailable')
        cmd=self.bot.tree.get_command('admin-set')
        with self.assertLogs(level='ERROR'):
            await cmd.callback(self.interaction,SimpleNamespace(id=20),'packs','8','reason')
        self.assertEqual(self.store.ranked('packs')[0][2],8)
        self.assertIn('refresh is pending',self.interaction.followup.send.call_args.args[0])
    async def test_bad_input_never_refreshes_or_changes_scores(self):
        await self.bot.tree.get_command('admin-set').callback(self.interaction,SimpleNamespace(id=20),'packs','-5','reason')
        self.assertEqual(self.store.ranked('packs')[0][2],100)
        self.bot.boards.assert_not_awaited()
        self.interaction.response.send_message.assert_awaited_once()

if __name__=='__main__':unittest.main()
