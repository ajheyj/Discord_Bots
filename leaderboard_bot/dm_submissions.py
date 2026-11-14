"""Server-only slash entry point opens a time-limited private DM upload session."""
import time
import discord
from discord import app_commands
from submission_results import result_embed

def register_submissions(bot,store,guild_id):
    @bot.tree.command(name='submit',description='Start a private screenshot submission in DMs')
    @app_commands.guild_only()
    async def submit(interaction:discord.Interaction):
        if interaction.guild_id!=guild_id:
            await interaction.response.send_message('Use this command in the leaderboard server.',ephemeral=True);return
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.user.send('**Leaderboard screenshot submission**\nSend one or two PNG, JPG or WebP screenshots per message here (up to 15 MB each). '
                'Include the Player Stats panel. I will save any confidently read stats and DM you what changed. '
                'Missing or unreadable stats stay unchanged. Your screenshots and results may be shared with the server’s configured moderator audit channel. '
                'This upload session lasts 24 hours; use /submit in the server again to reopen it.',
                allowed_mentions=discord.AllowedMentions.none())
        except discord.HTTPException:
            await interaction.followup.send('I could not DM you. Allow direct messages from this server, then run /submit again.',ephemeral=True);return
        with store.db:store.db.execute('INSERT OR REPLACE INTO dm_sessions VALUES(?,?)',(str(interaction.user.id),time.time()+86400))
        await interaction.followup.send('Check your DMs from me and send your screenshots there. Nothing is posted in this channel.',ephemeral=True)

    @bot.tree.command(name='submission-result',description='Privately view your latest screenshot result')
    @app_commands.guild_only()
    async def submission_result(interaction:discord.Interaction):
        if interaction.guild_id!=guild_id:
            await interaction.response.send_message('Use this command in the leaderboard server.',ephemeral=True);return
        row=store.db.execute('SELECT message,url FROM submission_results WHERE user=? ORDER BY time DESC LIMIT 1',(str(interaction.user.id),)).fetchone()
        if not row:
            await interaction.response.send_message('No completed result yet. Your submission may still be queued.',ephemeral=True);return
        await interaction.response.send_message(embed=result_embed(store.result(row[0]),row[1]),ephemeral=True)
