import asyncio
import json
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,Mock,patch
import discord
from store import Store
from queue_config import QueueConfig
from durable_jobs import DurableJobs,QueueRejected
from durable_service import DurablePipeline
from storage_tools import Spool,InstanceLock,backup_database
from ocr_process import run_ocr,JobError
from submission_replay import SubmissionReplay

NOW=datetime(2026,11,10,tzinfo=timezone.utc)
def config(root,**changes):
    values=dict(spool=Path(root)/'spool',backup_dir=Path(root)/'backups',backup_hours=0,min_free_bytes=0,retry_delay=0)
    values.update(changes);return QueueConfig(**values)
def message(mid=1,user=20,count=2):
    data=json.dumps({'message':mid}).encode()
    attachments=[SimpleNamespace(id=mid*10+i,filename=f'{i}.png',size=len(data),read=AsyncMock(return_value=data)) for i in range(count)]
    return SimpleNamespace(id=mid,author=SimpleNamespace(id=user,display_name='Discord Name',bot=False,send=AsyncMock()),
        guild=SimpleNamespace(id=99),channel=SimpleNamespace(id=123),created_at=NOW-timedelta(hours=1),
        jump_url=f'https://discord.com/channels/99/123/{mid}',attachments=attachments,reply=AsyncMock(),
        add_reaction=AsyncMock(),remove_reaction=AsyncMock())
def bot_and_channel(messages):
    channel=Mock(spec=discord.TextChannel);channel.guild=SimpleNamespace(id=99)
    channel.fetch_message=AsyncMock(side_effect=lambda mid:messages[mid])
    bot=SimpleNamespace(user=SimpleNamespace(id=777),fetch_channel=AsyncMock(return_value=channel),
        wait_until_ready=AsyncMock(),is_closed=lambda:False,reaction=AsyncMock(),mark_scores_changed=Mock())
    return bot,channel

class DurableStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.path=self.root/'db';self.store=Store(self.path);self.cfg=config(self.root)
        self.now=[1000.];self.jobs=DurableJobs(self.store,self.cfg,clock=lambda:self.now[0])
    def tearDown(self):self.store.db.close();self.temp.cleanup()
    def add(self,mid=1,user=20,replay=False):
        return self.jobs.admit(mid,user,'Name','url',NOW.isoformat(),[{'id':'1','filename':'x.png','size':10}],replay,10**12)
    def test_persistent_database_and_dedicated_storage_paths_required(self):
        for path in ('',':memory:'):
            with self.assertRaises(ValueError):Store(path)
        with patch.dict(os.environ,{'SPOOL_PATH':str(self.root)},clear=False):
            with self.assertRaises(ValueError):QueueConfig.from_env(self.path)
        with patch.dict(os.environ,{'SPOOL_PATH':str(self.root/'spool'),'BACKUP_PATH':str(self.root/'spool'/'backups')},clear=False):
            with self.assertRaises(ValueError):QueueConfig.from_env(self.path)
        with self.assertRaises(ValueError):backup_database(self.path,self.root)
    def test_admission_committed_and_duplicate_id_not_accepted_twice(self):
        self.assertTrue(self.add());self.assertFalse(self.add())
        other=sqlite3.connect(self.path)
        self.assertEqual(other.execute('SELECT state FROM queue_jobs').fetchone()[0],'download_wait');other.close()
    def test_global_per_user_and_disk_limits_reject_without_claiming_acceptance(self):
        self.cfg.per_user=1;self.add()
        with self.assertRaises(QueueRejected):self.add(2)
        self.cfg.per_user=5;self.cfg.max_jobs=1
        with self.assertRaises(QueueRejected):self.add(2,21)
        self.cfg.max_jobs=10;self.cfg.spool_bytes=15
        with self.assertRaises(QueueRejected):self.add(2,21)
        self.cfg.spool_bytes=100
        with self.assertRaises(QueueRejected):self.jobs.admit(2,21,'N','url',NOW.isoformat(),[{'size':10}],False,5)
        self.assertEqual(self.jobs.get(2),None)
    def test_restart_recovers_claims_and_preserves_attempt_counts(self):
        self.add();self.jobs.claim('download')
        self.store.db.close();self.store=Store(self.path);self.jobs=DurableJobs(self.store,self.cfg,clock=lambda:self.now[0])
        self.jobs.recover();row=self.jobs.claim('download')
        self.assertEqual(row['download_attempts'],2)
        self.jobs.ready(1);row=self.jobs.claim('ocr');self.assertEqual(row['ocr_attempts'],1)
        self.jobs.recover();self.assertEqual(self.jobs.claim('ocr')['ocr_attempts'],2)
    def test_retry_budget_and_backoff(self):
        self.add();self.cfg.retry_delay=10
        self.jobs.claim('download');self.assertTrue(self.jobs.retry(1,'download','temporary'))
        self.assertIsNone(self.jobs.claim('download'));self.now[0]+=10
        self.assertEqual(self.jobs.claim('download')['download_attempts'],2)
        self.assertTrue(self.jobs.retry(1,'download','temporary'));self.now[0]+=20
        self.jobs.claim('download');self.assertFalse(self.jobs.retry(1,'download','temporary'))
        self.jobs.fail(1,'exhausted');self.assertEqual(self.jobs.get(1)['state'],'failed')
    def test_interruption_cannot_evade_attempt_budget(self):
        self.add()
        for _ in range(3):self.jobs.claim('download');self.jobs.recover()
        self.assertIsNone(self.jobs.claim('download'))
        self.assertEqual(self.jobs.get(1)['state'],'failed')
        self.assertEqual(self.jobs.get(1)['download_attempts'],3)
    def test_score_commit_and_job_completion_are_atomic_and_idempotent(self):
        self.add();self.jobs.ready(1);self.jobs.claim('ocr')
        self.store.db.execute("CREATE TRIGGER block_done BEFORE UPDATE ON queue_jobs WHEN NEW.state='done' BEGIN SELECT RAISE(ABORT,'test'); END")
        values=dict(username='EPIC',packs=10,money=20,coins=30)
        with self.assertRaises(sqlite3.IntegrityError):self.jobs.succeed(1,values)
        self.assertFalse(self.store.seen(1));self.assertEqual(self.store.ranked('packs'),[])
        self.store.db.execute('DROP TRIGGER block_done')
        self.jobs.succeed(1,values);self.jobs.succeed(1,dict(packs=999,money=999,coins=999))
        self.assertEqual(self.store.ranked('packs')[0][2],10)
        self.assertEqual(self.jobs.get(1)['state'],'done')
    def test_existing_success_and_admin_correction_not_overwritten(self):
        self.store.record(1,20,'Name','url',dict(packs=10,money=20,coins=30))
        self.store.admin_change(30,20,'fix','packs',5)
        self.assertFalse(self.add())
        self.assertEqual(self.store.ranked('packs')[0][2],5)
    def test_terminal_failure_can_retry_on_new_startup_history_scan(self):
        self.add();self.jobs.claim('download');self.jobs.fail(1,'unreadable')
        self.assertFalse(self.add());self.assertTrue(self.add(replay=True))
        self.assertEqual(self.jobs.get(1)['state'],'download_wait')
        self.assertEqual(self.jobs.get(1)['download_attempts'],0)
    def test_single_instance_lock_and_consistent_wal_backups(self):
        lock=InstanceLock(self.root/'lock');other=InstanceLock(self.root/'lock');lock.acquire()
        try:
            with self.assertRaises(RuntimeError):other.acquire()
        finally:lock.close()
        other.acquire();other.close()
        self.add();self.store.record(2,20,'N','url',dict(packs=99,money=10**18+1,coins=4))
        paths=[backup_database(self.path,self.root/'backups',keep=2) for _ in range(3)]
        self.assertEqual(len(list((self.root/'backups').glob('*.sqlite3'))),2)
        backup=sqlite3.connect(paths[-1])
        self.assertEqual(backup.execute('SELECT money FROM scores').fetchone()[0],str(10**18+1))
        self.assertEqual(backup.execute('SELECT count(*) FROM queue_jobs').fetchone()[0],1)
        self.assertEqual(backup.execute('PRAGMA quick_check').fetchone()[0],'ok');backup.close()
    def test_spool_atomic_files_and_path_validation(self):
        spool=Spool(self.cfg.spool);self.add()
        spool.write(1,0,b'0123456789');self.assertTrue(spool.complete(self.jobs.get(1)))
        self.assertFalse(list(spool.directory(1).glob('*.part')))
        with self.assertRaises(ValueError):spool.directory('../escape')
        spool.delete(1);self.assertFalse(spool.complete(self.jobs.get(1)))

class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Store(self.root/'db');self.messages={1:message()}
        self.bot,self.channel=bot_and_channel(self.messages);self.cfg=config(self.root)
        self.pipeline=DurablePipeline(self.bot,self.store,99,123,self.cfg)
    async def asyncTearDown(self):await self.pipeline.close();self.store.db.close();self.temp.cleanup()
    async def test_acknowledgment_follows_durable_admission(self):
        replay=SubmissionReplay(self.bot,self.store,99,123,config=self.cfg)
        async def reaction(msg,emoji,*args):
            con=sqlite3.connect(self.store.path)
            self.assertEqual(con.execute('SELECT state FROM queue_jobs WHERE message=?',(str(msg.id),)).fetchone()[0],'download_wait');con.close()
        async def receipt(*args,**kwargs):await reaction(self.messages[1],None)
        self.messages[1].author.send.side_effect=receipt
        self.assertTrue(await replay.enqueue(self.messages[1]))
        self.assertFalse(await replay.enqueue(self.messages[1]))
    async def test_two_image_cache_survives_message_deletion_and_cleans_on_success(self):
        self.pipeline.admit(self.messages[1]);row=self.pipeline.jobs.claim('download');await self.pipeline.download(row)
        row=self.pipeline.jobs.claim('ocr')
        self.channel.fetch_message.side_effect=discord.NotFound(SimpleNamespace(status=404,reason='missing'),'missing')
        values=dict(username='EPIC',packs=10,money=20,coins=30,shiny=6,playtime=40)
        with patch('durable_service.run_ocr',new=AsyncMock(return_value=values)):await self.pipeline.process_ocr(row)
        self.assertTrue(self.store.seen(1));self.assertEqual(self.pipeline.jobs.reserved(),0)
        self.assertFalse(self.pipeline.spool.directory(1).exists())
    async def test_changed_attachments_are_not_silently_replaced(self):
        self.pipeline.admit(self.messages[1]);row=self.pipeline.jobs.claim('download')
        self.messages[1].attachments[0].id=999
        with self.assertRaises(JobError):await self.pipeline.download(row)
        self.assertFalse(self.store.seen(1))
    async def test_download_retry_reuses_first_file_without_redownloading_it(self):
        msg=self.messages[1];self.pipeline.admit(msg);row=self.pipeline.jobs.claim('download')
        msg.attachments[1].read.side_effect=OSError('temporary')
        with self.assertRaises(OSError):await self.pipeline.download(row)
        self.assertTrue(self.pipeline.spool.paths(row)[0].exists())
        self.pipeline.jobs.retry(1,'download','temporary');row=self.pipeline.jobs.claim('download')
        msg.attachments[1].read.side_effect=None;await self.pipeline.download(row)
        self.assertEqual(msg.attachments[0].read.await_count,1)
        self.assertEqual(self.pipeline.jobs.get(1)['state'],'ready')
    async def test_terminal_notification_failure_never_undoes_saved_score(self):
        self.pipeline.admit(self.messages[1]);self.pipeline.jobs.succeed(1,dict(packs=10,money=20,coins=30))
        row=self.pipeline.jobs.notifications()[0]
        self.bot.fetch_user=AsyncMock(return_value=SimpleNamespace(send=AsyncMock(side_effect=discord.Forbidden(SimpleNamespace(status=403,reason='denied'),'denied'))))
        await self.pipeline.notify(row)
        self.assertEqual(self.store.db.execute('SELECT dm_status FROM submission_results WHERE message="1"').fetchone()[0],'blocked')
        self.assertTrue(self.store.seen(1));self.assertEqual(self.pipeline.jobs.get(1)['state'],'done')
        self.assertEqual(self.pipeline.jobs.notifications(),[])
    async def test_failure_retention_and_pressure_cleanup_release_reserved_bytes(self):
        self.pipeline.admit(self.messages[1]);row=self.pipeline.jobs.get(1)
        for i,a in enumerate(self.messages[1].attachments):self.pipeline.spool.write(1,i,await a.read())
        self.pipeline.jobs.ready(1);await self.pipeline.finish_failure(row,'unreadable')
        self.assertGreater(self.pipeline.jobs.reserved(),0)
        self.pipeline.cleanup(evict_failed=True)
        self.assertEqual(self.pipeline.jobs.reserved(),0)
        self.assertFalse(self.pipeline.spool.directory(1).exists())
    async def test_queue_command_role_checks_are_retained(self):
        from admin_commands import register_admin
        client=discord.Client(intents=discord.Intents.none())
        try:
            fake=SimpleNamespace(tree=discord.app_commands.CommandTree(client),boards=AsyncMock())
            register_admin(fake,self.store,99,{'packs':('Packs',0)},str,role_id=456,queue_status=self.pipeline.status)
            cmd=fake.tree.get_command('queue');self.assertEqual(cmd.default_permissions.value,0)
            denied=SimpleNamespace(guild_id=99,user=SimpleNamespace(roles=[]),permissions=discord.Permissions(administrator=True))
            with self.assertRaises(discord.app_commands.CheckFailure):await cmd.checks[0](denied)
            denied.user.roles=[SimpleNamespace(id=456)];self.assertTrue(await cmd.checks[0](denied))
        finally:await client.close()

class SubprocessTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_forces_single_native_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'thread_check.py'
            script.write_text("import sys,json,os\nsys.path.insert(0,"+repr(str(Path(__file__).resolve().parents[1]))+")\nimport ocr_runner,cv2\nprint(json.dumps({'ok':True,'values':{'packs':int(os.environ['OMP_THREAD_LIMIT']),'coins':cv2.getNumThreads(),'money':int(os.environ['OPENBLAS_NUM_THREADS'])}}))\n")
            self.assertEqual(await run_ocr([],15,script),dict(packs=1,money=1,coins=1))
    @unittest.skipUnless(os.name=='posix','POSIX descendant termination check')
    async def test_timeout_kills_ocr_and_descendant_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'hang.py';pidfile=Path(tmp)/'child.pid'
            script.write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c','import time;time.sleep(120)'])\nPath(sys.argv[1]).write_text(str(p.pid))\ntime.sleep(120)\n")
            with self.assertRaises(JobError) as error:await run_ocr([pidfile],1,script)
            self.assertTrue(error.exception.retry)
            self.assertTrue(pidfile.exists())
            pid=int(pidfile.read_text());stat=Path(f'/proc/{pid}/stat')
            await asyncio.sleep(.05)
            self.assertTrue(not stat.exists() or stat.read_text().split()[2]=='Z','Descendant still running')

class BurstTests(unittest.IsolatedAsyncioTestCase):
    async def test_500_two_image_jobs_survive_restart_and_reach_terminal_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg=config(root,max_jobs=600,per_user=2)
            messages={100000+i:message(100000+i,user=200000+i) for i in range(1,501)}
            bot,channel=bot_and_channel(messages);store=Store(root/'db')
            pipeline=DurablePipeline(bot,store,99,123,cfg)
            for msg in messages.values():self.assertTrue(pipeline.admit(msg))
            self.assertEqual(pipeline.jobs.counts(),{'download_wait':500})
            downloads=[0,0];ocrs=[0,0];download_fail=set();ocr_fail=set();interrupted=asyncio.Event();phase=[0]
            for mid,msg in messages.items():
                for index,attachment in enumerate(msg.attachments):
                    async def read(mid=mid,index=index):
                        downloads[0]+=1;downloads[1]=max(downloads[1],downloads[0])
                        try:
                            await asyncio.sleep(.001)
                            if (mid-100000)%19==0 and index==1 and mid not in download_fail:
                                download_fail.add(mid);raise OSError('simulated temporary download failure')
                            return json.dumps({'message':mid}).encode()
                        finally:downloads[0]-=1
                    attachment.read.side_effect=read
            async def fake_ocr(paths,timeout):
                mid=int(paths[0].parent.name);index=mid-100000
                self.assertTrue(all(path.exists() for path in paths));self.assertEqual(len(paths),2)
                ocrs[0]+=1;ocrs[1]=max(ocrs[1],ocrs[0])
                try:
                    if index==125 and phase[0]==0:
                        interrupted.set();await asyncio.Event().wait()
                    await asyncio.sleep(.001)
                    if index%17==0:raise JobError('simulated unreadable image',retry=False)
                    if index%13==0 and mid not in ocr_fail:
                        ocr_fail.add(mid);raise JobError('simulated temporary OCR error',retry=True)
                    return dict(username='EPIC_'+str(index),packs=index,money=index*10**18,coins=index,shiny=index,playtime=index)
                finally:ocrs[0]-=1
            with patch('durable_service.run_ocr',new=fake_ocr),patch('logging.exception'),patch('logging.warning'):
                pipeline.start()
                try:await asyncio.wait_for(interrupted.wait(),30)
                finally:await pipeline.close()
                self.assertGreater(sum(pipeline.jobs.counts().get(k,0) for k in ('done','failed')),0)
                store.db.close();store=Store(root/'db')
                pipeline=DurablePipeline(bot,store,99,123,cfg);phase[0]=1;pipeline.start()
                try:
                    deadline=time.monotonic()+30
                    while sum(pipeline.jobs.counts().get(k,0) for k in ('done','failed'))<500:
                        self.assertLess(time.monotonic(),deadline,'Queue failed to drain')
                        await asyncio.sleep(.02)
                    self.assertEqual(pipeline.jobs.counts(),{'done':471,'failed':29})
                    self.assertEqual(len(store.ranked('packs')),471)
                    self.assertEqual(pipeline.jobs.db.execute('SELECT count(*) FROM queue_jobs').fetchone()[0],500)
                    self.assertEqual(ocrs[1],1);self.assertLessEqual(downloads[1],2)
                    # Once terminal failed images are evicted, every storage reservation is released.
                    pipeline.cleanup(evict_failed=True);self.assertEqual(pipeline.jobs.reserved(),0)
                    self.assertFalse(any(pipeline.spool.root.iterdir()))
                    self.assertEqual(store.db.execute('SELECT count(*) FROM submission_failures').fetchone()[0],29)
                finally:await pipeline.close();store.db.close()

if __name__=='__main__':unittest.main()
