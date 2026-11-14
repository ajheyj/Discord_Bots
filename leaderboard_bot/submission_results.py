"""Private and moderator summaries share the same committed before/after snapshot."""
from decimal import Decimal
import discord
from ocr import SUFFIXES

LABELS={'packs':'Packs Opened','money':'Money Earned','coins':'Grade Coins',
        'shiny':'Shiny Cards','playtime':'Total Playtime'}

def display(key,value):
    if value is None:return 'Not recorded'
    if key=='playtime':
        days,seconds=divmod(value,86400);hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
        return f'{days:02d}d {hours:02d}h {minutes:02d}m {seconds:02d}s'
    if key=='money':
        for suffix,power in reversed(list(SUFFIXES.items())):
            if value>=10**power:return '$'+format(Decimal(value)/Decimal(10**power),'.3f').rstrip('0').rstrip('.')+suffix
        return '$0'
    return f'{value:,}'

def result_embed(payload,url=None):
    error=payload.get('error');recognized=payload.get('recognized',{})
    embed=discord.Embed(title='Screenshot could not be processed' if error else 'Screenshot results',
                        color=0xE74C3C if error else 0x2ECC71)
    if error:embed.description=str(error)[:1000]
    if payload.get('username'):
        embed.add_field(name='Epic name',value=discord.utils.escape_markdown(discord.utils.escape_mentions(payload['username'])),inline=False)
    before,after=payload.get('before',{}),payload.get('after',{})
    for key,label in LABELS.items():
        old,new=before.get(key),after.get(key)
        if key not in recognized:
            line=f'Not read in this submission. Saved: {display(key,new)}.'
        elif new!=old:
            line=f'{display(key,old)} → **{display(key,new)}**'
        else:
            line=f'No change. Read: {display(key,recognized[key])}; saved best: {display(key,new)}.'
        embed.add_field(name=label,value=line,inline=False)
    warnings=payload.get('warnings',[])
    if warnings:embed.add_field(name='Recognition notes',value='\n'.join(dict.fromkeys(str(w) for w in warnings))[:1000],inline=False)
    if url:embed.add_field(name='Submission',value=f'[Open your original message]({url})',inline=False)
    embed.set_footer(text='Scores belong to your Discord account. Unreadable stats stay unchanged; lifetime bests never decrease.')
    return embed
