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

    def embed(self, row):
        audit_id, actor, user, time, action, category, before, after, reason = row
        before, after = json.loads(before), json.loads(after)
        embed = discord.Embed(title='Score corrected' if action == 'set' else 'Player removed',
                              color=0xE5B83B if action == 'set' else 0xE74C3C,
                              timestamp=datetime.fromisoformat(time))
        embed.add_field(name='Moderator', value=f'<@{actor}>\nID: {actor}')
        embed.add_field(name='Player', value=f'<@{user}>\nID: {user}')
        keys = (category,) if category else ('packs', 'money', 'coins')
        for key in keys:
            # Show the exact stored integers as well as the abbreviated display.
            old = f'{self.display(key,before[key])} (exact: {before[key]})'
            new = f'{self.display(key,after[key])} (exact: {after[key]})' if after else 'Removed'
            embed.add_field(name=self.categories[key][0], value=f'Before: {old}\nAfter: {new}', inline=False)
        embed.add_field(name='Reason', value=discord.utils.escape_markdown(reason), inline=False)
        embed.set_footer(text=f'Admin audit #{audit_id}')
        return embed

    async def flush(self):
        if not self.channel_id:
            return
        async with self.lock:
            rows = self.store.pending_admin_audits()
            if not rows:
                return
            channel = await self.bot.fetch_channel(self.channel_id)
            if not isinstance(channel, discord.TextChannel) or channel.guild.id != self.guild_id:
                raise ValueError('AUDIT_CHANNEL_ID must be a text channel in the configured server.')
            for row in rows:
                message = await channel.send(embed=self.embed(row), allowed_mentions=discord.AllowedMentions.none())
                self.store.mark_admin_delivered(row[0], message.id)
