"""Durable stages: admission -> bounded download pool -> one OCR subprocess -> notification."""
import asyncio
import json
import logging
import os
import shutil
import time
from datetime import datetime,timezone
import discord
from durable_jobs import DurableJobs, QueueRejected
from storage_tools import Spool, InstanceLock, backup_database
from ocr_process import run_ocr, JobError

class DurablePipeline:
    def __init__(self,bot,store,guild_id,channel_id,config):
        self.bot,self.store,self.guild_id,self.channel_id=bot,store,guild_id,channel_id
        self.config=config;self.jobs=DurableJobs(store,config);self.spool=Spool(config.spool)
        self.lock=InstanceLock(str(store.path)+'.worker.lock')
        self.tasks={};self.wake=asyncio.Event();self.ocr_message=None
        self.audit_enabled=bool(getattr(bot,'audit_channel_id',0))
        self.last_backup=None;self.last_error=None;self.channel=None

    async def source_channel(self):
        if self.channel is None:
            channel=await self.bot.fetch_channel(self.channel_id)
            if not isinstance(channel,discord.TextChannel) or channel.guild.id!=self.guild_id:
                raise ValueError('Submissions channel must be a text channel in the configured server.')
            self.channel=channel
        return self.channel

    def admit(self,msg,replay=False):
        attachments=[]
        if not 1<=len(msg.attachments)<=2:raise QueueRejected('Attach one or two screenshots per message.')
        for attachment in msg.attachments:
            if not attachment.filename.lower().endswith(('.png','.jpg','.jpeg','.webp')):
                raise QueueRejected('Use PNG, JPG or WebP screenshots.')
            if not 0<attachment.size<=15*1024*1024:raise QueueRejected('Each image must be no larger than 15 MB.')
            attachments.append({'id':str(attachment.id),'filename':attachment.filename,'size':attachment.size})
        free=shutil.disk_usage(self.config.spool).free
        try:
            admitted=self.jobs.admit(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,
                msg.created_at.astimezone(timezone.utc).isoformat(),attachments,replay,free,source_channel=msg.channel.id)
        except QueueRejected as error:
            # Under storage pressure, evict only terminal-job cached files before rejecting admission.
            if 'storage' not in str(error).lower():raise
            self.cleanup(evict_failed=True)
            free=shutil.disk_usage(self.config.spool).free
            admitted=self.jobs.admit(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,
                msg.created_at.astimezone(timezone.utc).isoformat(),attachments,replay,free,source_channel=msg.channel.id)
        if admitted:self.wake.set()
        return admitted

    def cleanup(self,evict_failed=False):
        cutoff=time.time()-self.config.failed_retention_hours*3600
        for row in self.jobs.rows("SELECT * FROM queue_jobs WHERE state IN ('done','failed') AND reserved>0"):
            report=self.store.db.execute('SELECT delivered_message FROM submission_results WHERE message=?',(row['message'],)).fetchone()
            delivered=not self.audit_enabled or bool(report and report[0])
            if (row['state']=='done' and delivered) or evict_failed or (row['finished'] is not None and row['finished']<=cutoff):
                self.spool.delete(row['message']);self.jobs.release_files(row['message'])
        # The configured spool is dedicated to this bot. Recover orphan files left by a DB restore.
        for path in self.spool.root.iterdir():
            if path.is_dir() and path.name.isdigit() and self.jobs.get(path.name) is None:
                self.spool.delete(path.name)

    def recover(self,stale_before=None):
        for row in self.jobs.recover(stale_before):
            counter=row['ocr_attempts'] if row['state']=='ocr_running' else row['download_attempts']
            if counter>=self.config.attempts:
                self.jobs.fail(row['message'],'Attempt limit reached after repeated processing interruptions.')
        for row in self.jobs.rows("SELECT * FROM queue_jobs WHERE state IN ('ready','ocr_retry') AND spooled=1"):
            if not self.spool.complete(row):self.jobs.need_download(row['message'])

    def start(self):
        self.lock.acquire()
        try:
            self.recover();self.cleanup()
            self.spawn('ocr',self.ocr_loop)
            for i in range(self.config.download_workers):self.spawn('download-'+str(i),self.download_loop)
            self.spawn('notify',self.notification_loop)
            self.spawn('maintenance',self.maintenance_loop)
            self.spawn('supervisor',self.supervisor_loop)
        except Exception:
            self.lock.close();raise

    def spawn(self,name,operation):self.tasks[name]=asyncio.create_task(operation(),name='leaderboard-'+name)

    async def close(self):
        tasks=list(self.tasks.values())
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
        self.tasks.clear();self.lock.close()

    async def pause(self,seconds=1):
        self.wake.clear()
        try:await asyncio.wait_for(self.wake.wait(),seconds)
        except asyncio.TimeoutError:pass

    async def download(self,row):
        if self.spool.complete(row):
            self.jobs.ready(row['message']);self.wake.set();return
        channel=await self.bot.fetch_channel(int(row['source_channel'])) if row.get('source_channel') else await self.source_channel()
        msg=await channel.fetch_message(int(row['message']))
        if str(msg.author.id)!=row['user']:raise JobError('Original message uploader no longer matches the accepted submission.')
        actual={str(a.id):a for a in msg.attachments}
        for index,expected in enumerate(json.loads(row['attachments'])):
            attachment=actual.get(expected['id'])
            if attachment is None or attachment.size!=expected['size']:
                raise JobError('Original attachments were removed or changed before they were cached.')
            path=self.spool.paths(row)[index]
            if path.is_file() and path.stat().st_size==expected['size']:continue
            data=await attachment.read()
            if len(data)!=expected['size'] or len(data)>15*1024*1024:
                raise JobError('Attachment size does not match its accepted metadata.')
            await asyncio.to_thread(self.spool.write,row['message'],index,data)
        self.jobs.ready(row['message']);self.wake.set()

    async def finish_failure(self,row,reason):
        self.jobs.fail(row['message'],reason)
        self.last_error=reason
        if not self.config.failed_retention_hours:
            self.spool.delete(row['message']);self.jobs.release_files(row['message'])
        self.wake.set()

    async def stage_error(self,row,stage,error):
        from submission_replay import failure_reason
        reason=str(error) if isinstance(error,JobError) else failure_reason(error)
        retry=error.retry if isinstance(error,JobError) else isinstance(error,(asyncio.TimeoutError,TimeoutError,OSError,discord.HTTPException))
        if isinstance(error,(discord.NotFound,discord.Forbidden)):retry=False
        if isinstance(error,(asyncio.TimeoutError,TimeoutError)):
            reason='Attachment download timed out.' if stage=='download' else 'OCR job timed out.'
        if retry and self.jobs.retry(row['message'],stage,reason):
            self.last_error=reason;logging.warning('%s retry scheduled for %s: %s',stage,row['message'],reason)
        else:
            if retry:reason+=f' Retry budget exhausted ({self.config.attempts} attempts). '
            await self.finish_failure(row,reason.strip())

    async def download_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            row=self.jobs.claim('download')
            if not row:await self.pause();continue
            try:await asyncio.wait_for(self.download(row),self.config.download_timeout)
            except asyncio.CancelledError:raise
            except Exception as error:
                logging.exception('Download stage failed for %s',row['message'])
                self.last_error='Download stage encountered an error; inspect service logs.'
                await self.stage_error(row,'download',error)

    async def process_ocr(self,row):
        if self.store.seen(row['message']):
            # A previous save was committed; never replace an admin correction with a replay.
            self.jobs.succeed(row['message'],{})
        elif not self.spool.complete(row):
            self.jobs.need_download(row['message']);return
        else:
            values=await run_ocr(self.spool.paths(row),self.config.ocr_timeout)
            self.jobs.succeed(row['message'],values)
            self.bot.mark_scores_changed()
        if not self.audit_enabled:
            self.spool.delete(row['message']);self.jobs.release_files(row['message'])
        self.wake.set()

    async def ocr_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            row=self.jobs.claim('ocr')
            if not row:await self.pause();continue
            self.ocr_message=row['message']
            try:await self.process_ocr(row)
            except asyncio.CancelledError:raise
            except Exception as error:
                logging.exception('OCR stage failed for %s',row['message'])
                self.last_error='OCR stage encountered an error; inspect service logs.'
                # A score committed before a cleanup/notification failure stays successful.
                if self.store.seen(row['message']):
                    self.jobs.succeed(row['message'],{});self.bot.mark_scores_changed()
                else:await self.stage_error(row,'ocr',error)
            finally:self.ocr_message=None

    async def notify(self,row):
        from submission_results import result_embed
        current=self.jobs.get(row['message'])
        if current['state']!=row['state'] or current['error']!=row['error']:return
        delivery=self.store.db.execute('SELECT dm_status FROM submission_results WHERE message=?',(row['message'],)).fetchone()
        if delivery and delivery[0] in ('sent','blocked'):
            self.jobs.notified(row['message']);return
        payload=self.store.result(row['message'])
        if payload is None:
            self.jobs.notified(row['message']);return
        try:
            user=await self.bot.fetch_user(int(row['user']))
            await user.send(embed=result_embed(payload,row['url']),allowed_mentions=discord.AllowedMentions.none())
        except discord.Forbidden:
            if self.store.result(row['message'])!=payload:return
            # A blocked DM is permanent; /submission-result remains available privately.
            with self.store.db:self.store.db.execute("UPDATE submission_results SET dm_status='blocked' WHERE message=?",(row['message'],))
        else:
            if self.store.result(row['message'])!=payload:return
            with self.store.db:self.store.db.execute("UPDATE submission_results SET dm_status='sent' WHERE message=?",(row['message'],))
        self.jobs.notified(row['message'])

    async def notification_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            for row in self.jobs.notifications():
                try:await self.notify(row)
                except discord.NotFound:self.jobs.notified(row['message'])
                except asyncio.CancelledError:raise
                except Exception:
                    logging.exception('Reaction delivery pending for %s',row['message'])
                    self.jobs.notification_retry(row['message'])
            await asyncio.sleep(5)

    async def maintenance_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                self.cleanup()
                backups=sorted(self.config.backup_dir.glob('leaderboard-*.sqlite3'))
                last=backups[-1].stat().st_mtime if backups else 0
                if backups:self.last_backup=backups[-1].name
                if self.config.backup_hours and time.time()-last>=self.config.backup_hours*3600:
                    path=await asyncio.to_thread(backup_database,self.store.path,self.config.backup_dir,self.config.backup_keep)
                    self.last_backup=path.name;logging.info('Consistent database backup completed.')
            except Exception:
                logging.exception('Storage maintenance/backup failed');self.last_error='Storage maintenance or backup failed; check service logs.'
            await asyncio.sleep(60)

    async def supervisor_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                for name,task in list(self.tasks.items()):
                    if name=='supervisor' or not task.done():continue
                    if not task.cancelled():logging.error('Queue task %s stopped unexpectedly: %r',name,task.exception())
                    operation=self.download_loop if name.startswith('download-') else {'ocr':self.ocr_loop,'notify':self.notification_loop,'maintenance':self.maintenance_loop}[name]
                    self.spawn(name,operation)
                # Healthy stages finish inside these deadlines; only abandoned stale claims are reclaimed.
                self.recover(time.time()-max(self.config.download_timeout,self.config.ocr_timeout)-60)
            except Exception:
                logging.exception('Queue supervision failed; retrying in 30 seconds.')
                self.last_error='Queue supervision encountered an error; inspect service logs.'
            await asyncio.sleep(30)

    def status(self):
        counts=self.jobs.counts();oldest=self.jobs.oldest()
        pending=sum(counts.get(s,0) for s in ('download_wait','downloading','ready','ocr_running','ocr_retry'))
        age=f'{int((time.time()-oldest)/60)} minutes' if oldest else 'none'
        return ('**Queue status**\n'
            f'Pending: {pending} / {self.config.max_jobs}\n'
            f'Job totals done/failed: {counts.get("done",0)} / {counts.get("failed",0)}\n'
            f'Download waiting/running: {counts.get("download_wait",0)} / {counts.get("downloading",0)}\n'
            f'OCR ready/retry/running: {counts.get("ready",0)} / {counts.get("ocr_retry",0)} / {counts.get("ocr_running",0)}\n'
            f'Oldest pending age: {age}\n'
            f'Reserved image storage: {self.jobs.reserved()/1024**2:.1f} / {self.config.spool_bytes/1024**2:.0f} MiB\n'
            f'OCR worker: {"processing" if self.ocr_message else "waiting"}\n'
            f'Last backup: {self.last_backup or ("not yet recorded" if self.config.backup_hours else "disabled")}\n'
            f'Last issue: {self.last_error or "none recorded this startup"}')
