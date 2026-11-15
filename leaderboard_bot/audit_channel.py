"""Durable delivery of admin edit logs to a configured Discord text channel."""
import asyncio
import json
from datetime import datetime
import discord

class AuditChannel:
    def __init__(self, bot, store, guild_id, channel_id, categories, display):
        self.bot, self.store = bot, store
        self.guild_id, self.channel_id = guild_id, channel_id
        self.categories, self.display = categories, display
        self.lock = asyncio.Lock()

    @staticmethod
    def read_status(data):
        recognized=data.get('recognized') or {}
        if not recognized:return 'failed'
        if data.get('warnings') or not all(key in recognized for key in ('packs','money','coins','shiny')):
            return 'partial'
        return 'successful'

    async def submission_thread(self, channel, kind):
        names={'successful':'Complete reads','partial':'Partial reads','failed':'Failed reads'}
        if kind not in names:raise ValueError('Unknown submission audit status')
        self.store.db.execute('CREATE TABLE IF NOT EXISTS audit_threads(kind TEXT PRIMARY KEY,channel TEXT,thread TEXT)')
        self.store.db.commit()
        saved=self.store.db.execute('SELECT channel,thread FROM audit_threads WHERE kind=?',(kind,)).fetchone()
        thread=None
        if saved and saved[0]==str(channel.id):
            try:thread=await self.bot.fetch_channel(int(saved[1]))
            except discord.NotFound:pass
        if thread is not None:
            if not isinstance(thread,discord.Thread) or thread.parent_id!=channel.id or thread.guild.id!=self.guild_id:
                raise ValueError('Saved audit thread does not belong to the configured audit channel.')
            changes={}
            if thread.archived:changes['archived']=False
            if thread.name!=names[kind]:changes['name']=names[kind]
            if changes:await thread.edit(**changes)
        else:
            thread=await channel.create_thread(name=names[kind],
                type=discord.ChannelType.public_thread,auto_archive_duration=10080,
                reason='Separate leaderboard submission audits')
            with self.store.db:self.store.db.execute('INSERT OR REPLACE INTO audit_threads VALUES(?,?,?)',
                (kind,str(channel.id),str(thread.id)))
        return thread

    def embed(self, row):
        audit_id, actor, user, time, action, category, before, after, reason = row
        before, after = json.loads(before), json.loads(after)
        embed = discord.Embed(title='Score corrected' if action == 'set' else 'Player removed',
                              color=0xE5B83B if action == 'set' else 0xE74C3C,
                              timestamp=datetime.fromisoformat(time))
        embed.add_field(name='Moderator', value=f'<@{actor}>\nID: {actor}')
        embed.add_field(name='Player', value=f'<@{user}>\nID: {user}')
        keys = (category,) if category else tuple(key for key in before if key in self.categories)
        for key in keys:
            # Show the exact stored integers as well as the abbreviated display.
            old = f'{self.display(key,before[key])} (exact: {before[key]})' if key in before else 'Not recorded'
            new = f'{self.display(key,after[key])} (exact: {after[key]})' if after else 'Removed'
            embed.add_field(name=self.categories[key][0], value=f'Before: {old}\nAfter: {new}', inline=False)
        embed.add_field(name='Reason', value=discord.utils.escape_markdown(reason), inline=False)
        embed.set_footer(text=f'Admin audit #{audit_id}')
        return embed

    def failure_embed(self, row):
        failure_id,message_id,user,url,time,reason = row
        embed = discord.Embed(title='Screenshot processing failed',color=0xE74C3C,
                              description=f'[Open original image message]({url})',
                              timestamp=datetime.fromisoformat(time))
        embed.add_field(name='Player',value=f'<@{user}>\nID: {user}')
        embed.add_field(name='Message ID',value=message_id)
        embed.add_field(name='Reason',value=discord.utils.escape_markdown(reason),inline=False)
        if self.store.seen(message_id):
            embed.add_field(name='Current status',value='This submission has since processed successfully.',inline=False)
        embed.set_footer(text=f'Submission failure #{failure_id} • same message/reason logged once')
        return embed

    async def flush(self):
        if not self.channel_id:
            return
        async with self.lock:
            rows = self.store.pending_admin_audits()
            failures = [r for r in self.store.pending_submission_failures() if self.store.result(r[1]) is None]
            results=self.store.db.execute('SELECT message,user,url,payload,dm_status FROM submission_results WHERE delivered_message IS NULL ORDER BY time LIMIT 20').fetchall()
            if not rows and not failures and not results:
                return
            channel = await self.bot.fetch_channel(self.channel_id)
            if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.guild_id:
                raise ValueError('AUDIT_CHANNEL_ID must be a text channel in the configured server.')
            for row in rows:
                message = await channel.send(embed=self.embed(row), allowed_mentions=discord.AllowedMentions.none())
                self.store.mark_admin_delivered(row[0], message.id)
            for row in failures:
                target=await self.submission_thread(channel,'failed')
                message = await target.send(embed=self.failure_embed(row), allowed_mentions=discord.AllowedMentions.none())
                self.store.mark_failure_delivered(row[0], message.id)

            from submission_results import result_embed
            from pathlib import Path
            for mid,user,url,payload,dm_status in results:
                data=json.loads(payload)
                embed=result_embed(data,url)
                if data.get('recognized'):
                    exact='\n'.join(f'{key}: {value} → {data.get("after",{}).get(key,"not recorded")}' for key,value in ((k,data.get('before',{}).get(k,'not recorded')) for k in data.get('after',{})))
                    if exact:embed.add_field(name='Exact saved values (before → after)',value=exact[:1000],inline=False)
                embed.add_field(name='Discord account',value=f'<@{user}> (ID: {user})',inline=False)
                embed.add_field(name='Private delivery',value=dm_status or 'Pending; /submission-result also available',inline=False)
                files=[];skipped=0
                # A DM jump link is visible only to its participants. Copy cached images to the audit channel.
                config=getattr(self.bot,'config',None)
                root=Path(config.spool) if config else self.store.path.parent/'spool'
                for path in sorted((root/str(mid)).glob('*.img'))[:2]:
                    if path.stat().st_size<=channel.guild.filesize_limit:
                        files.append(discord.File(path,filename=f'submission-{mid}-{path.stem}.png'))
                    else:skipped+=1
                if skipped:embed.add_field(name='Omitted attachments',value=f'{skipped} image(s) exceed the audit channel upload limit.',inline=False)
                if not files:
                    embed.add_field(name='Images',value='Cached images unavailable or exceed the audit channel upload limit. DM links are private to the submitter.',inline=False)
                try:
                    target=await self.submission_thread(channel,self.read_status(data))
                    message=await target.send(embed=embed,files=files,allowed_mentions=discord.AllowedMentions.none())
                finally:
                    for file in files:file.close()
                with self.store.db:
                    self.store.db.execute('UPDATE submission_results SET delivered_message=? WHERE message=? AND payload=?',(str(message.id),mid,payload))
                    self.store.db.execute('UPDATE submission_failures SET delivered_message=? WHERE message=? AND delivered_message IS NULL',(str(message.id),mid))
