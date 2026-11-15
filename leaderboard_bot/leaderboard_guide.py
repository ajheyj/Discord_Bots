"""One persistent instruction message, before the bot's scoreboard message slots."""
import logging
import discord

KEY='instructions'
def guide_embed():
    embed=discord.Embed(title='How to use the leaderboard',color=0x3498DB,
        description='1. Run **/submit** in this server. Only you see the command reply.\n'
        '2. Check your DMs from this bot and send **one or two screenshots of your own stats** per message (PNG, JPG or WebP; up to 15 MB each). '
        'Two images in one message must belong to the same player. Your session lasts 24 hours; /submit reopens it.\n'
        '3. Wait for the private result summary. Busy queues can take time—avoid duplicate uploads.\n'
        '4. Use **/submission-result** for your latest result, **/rank** for your standings or **/leaderboard** to browse rankings privately.')
    embed.add_field(name='Capture the stats',value='Open Player Stats, include your username and visible values. Send a second scrolled view for playtime. Direct screenshots work best; avoid blur, glare and tilted monitor photos.',inline=False)
    embed.add_field(name='Partial reads and identity',value='Each confidently read stat saves independently. Unreadable/off-screen fields stay unchanged and lifetime bests never decrease. Your Discord account owns your scores, so an Epic name change does not create a second entry.',inline=False)
    embed.add_field(name='Privacy and help',value='Public boards show your name and scores. The bot operator and authorized moderator audit-channel viewers may see screenshots and submission results. Allow server DMs if /submit cannot reach you. Ask a moderator about incorrect scores or privacy requests. '
        '[Privacy](https://github.com/ajheyj/Discord_Bots/blob/main/PRIVACY.md) · [Terms](https://github.com/ajheyj/Discord_Bots/blob/main/TERMS.md)',inline=False)
    return embed

async def ensure_guide(bot,store,channel,categories):
    embed=guide_embed();message=None
    mid=store.board(KEY)
    if mid:
        try:message=await channel.fetch_message(mid)
        except discord.NotFound:pass
        if message is not None and message.author.id!=bot.user.id:
            raise ValueError('Saved guide message does not belong to this bot.')
    if message is None:
        existing={}
        for key in categories:
            mid=store.board(key)
            if not mid:continue
            try:old=await channel.fetch_message(mid)
            except discord.NotFound:continue
            if old.author.id==bot.user.id:existing[old.id]=old
        ordered=sorted(existing)
        if ordered:
            # Discord cannot move messages. Reuse only this bot's scoreboard slots, without deleting messages.
            message=existing[ordered[0]]
            with store.db:
                store.db.execute('INSERT OR REPLACE INTO boards VALUES(?,?)',(KEY,str(message.id)))
                for i,key in enumerate(categories):
                    if i+1<len(ordered):store.db.execute('INSERT OR REPLACE INTO boards VALUES(?,?)',(key,str(ordered[i+1])))
                    else:store.db.execute('DELETE FROM boards WHERE category=?',(key,))
        else:
            message=await channel.send(embed=embed,allowed_mentions=discord.AllowedMentions.none())
            store.save_board(KEY,message.id)
    old=message.embeds[0] if message.embeds else None
    if old is None or old.to_dict()!=embed.to_dict():await message.edit(embed=embed)
    if not message.pinned:
        try:await message.pin(reason='Leaderboard submission instructions')
        except discord.Forbidden:logging.warning('Cannot pin leaderboard guide; grant pin permission or pin it manually.')
    return message
