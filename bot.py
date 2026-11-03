import asyncio,logging,os
from decimal import Decimal
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from ocr import extract,OCRFailure,SUFFIXES
from store import Store
load_dotenv()
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
GUILD=int(os.environ['GUILD_ID']); SUB=int(os.environ['SUBMISSIONS_CHANNEL_ID']); BOARD=int(os.environ['LEADERBOARD_CHANNEL_ID'])
DB=Store(os.getenv('DATABASE_PATH','data/leaderboard.sqlite3'))
META={'packs':('📦 Packs Opened',0xE5B83B),'money':('💰 Total Money Earned',0x2ECC71),'coins':('🪙 Grade Coins Earned',0x9B59B6)}
def display(key,value):
    if key!='money': return f'{value:,}'
    for suffix,power in reversed(list(SUFFIXES.items())):
        if value>=10**power:
            return '$'+format(Decimal(value)/Decimal(10**power),'.3f').rstrip('0').rstrip('.')+suffix
    return '$0'
class Bot(discord.Client):
    def __init__(self):
        intents=discord.Intents.default(); intents.message_content=True
        super().__init__(intents=intents,allowed_mentions=discord.AllowedMentions.none())
        self.tree=app_commands.CommandTree(self); self.lock=asyncio.Lock(); self.queue=asyncio.Queue(maxsize=50)
    async def setup_hook(self):
        self.tree.copy_global_to(guild=discord.Object(id=GUILD))
        await self.tree.sync(guild=discord.Object(id=GUILD))
        self.worker=asyncio.create_task(self.work()); self.refresh.start()
    async def reaction(self,msg,emoji,remove=False):
        try:
            if remove: await msg.remove_reaction(emoji,self.user)
            else: await msg.add_reaction(emoji)
        except discord.HTTPException: logging.warning('Reaction failed for message %s',msg.id)
    async def on_message(self,msg):
        if msg.author.bot or msg.guild is None or msg.guild.id!=GUILD or msg.channel.id!=SUB or not msg.attachments: return
        if DB.seen(msg.id): await self.reaction(msg,'✅'); return
        if len(msg.attachments)!=1:
            await self.reaction(msg,'❌'); await msg.reply('Please attach one screenshot per message.',mention_author=False); return
        try: self.queue.put_nowait(msg)
        except asyncio.QueueFull:
            await self.reaction(msg,'❌'); return
        await self.reaction(msg,'⏳')
    async def work(self):
        await self.wait_until_ready()
        while not self.is_closed():
            msg=await self.queue.get()
            try:
                a=msg.attachments[0]
                if a.size>15*1024*1024: raise OCRFailure('Image exceeds 15 MB')
                if not a.filename.lower().endswith(('.png','.jpg','.jpeg','.webp')): raise OCRFailure('Use PNG, JPG or WebP')
                values=await asyncio.to_thread(extract,await a.read())
                DB.record(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,values)
                await self.reaction(msg,'✅')
                try: await self.boards()
                except Exception: logging.exception('Leaderboard update pending; periodic refresh will retry')
            except Exception as e:
                logging.exception('Submission failed: %s',msg.id)
                try: DB.record(msg.id,msg.author.id,msg.author.display_name,msg.jump_url,error=str(e))
                except Exception: logging.exception('Audit write failed')
                await self.reaction(msg,'❌')
                try: await msg.reply('Could not process this image. Please upload one clearer screenshot with all three stats visible.',mention_author=False)
                except discord.HTTPException: pass
            finally:
                await self.reaction(msg,'⏳',True); self.queue.task_done()
    async def boards(self):
        async with self.lock:
            channel=await self.fetch_channel(BOARD)
            if channel.guild.id!=GUILD: raise ValueError('Leaderboard channel belongs to another server')
            for key,(title,color) in META.items():
                all_rows=DB.ranked(key); rows=all_rows[:10]
                lines=[f'**{1+sum(r[2]>v for r in all_rows)}.** <@{u}> — **{display(key,v)}**' for u,n,v in rows]
                embed=discord.Embed(title=title+' — Top 10',description='\n'.join(lines) or 'No submissions yet.',color=color)
                embed.set_footer(text='All-time personal bests • /rank • /leaderboard')
                mid=DB.board(key); message=None
                if mid:
                    try: message=await channel.fetch_message(mid)
                    except discord.NotFound: pass
                if message: await message.edit(embed=embed)
                else:
                    message=await channel.send(embed=embed); DB.save_board(key,message.id)
                if not message.pinned:
                    try: await message.pin(reason='Leaderboard')
                    except discord.Forbidden: logging.warning('Pin permission missing; manually pin leaderboard messages')
    @tasks.loop(minutes=2)
    async def refresh(self):
        try: await self.boards()
        except Exception: logging.exception('Leaderboard refresh failed')
    @refresh.before_loop
    async def before_refresh(self): await self.wait_until_ready()
bot=Bot()
@bot.tree.command(description='View your personal standings in all three categories')
@app_commands.guild_only()
async def rank(interaction:discord.Interaction):
    lines=[]
    for key,(title,_) in META.items():
        rows=DB.ranked(key); found=next(((i,u,n,v) for i,(u,n,v) in enumerate(rows,1) if u==str(interaction.user.id)),None)
        if found:
            i,u,n,v=found; position=1+sum(r[2]>v for r in rows)
            lines.append(f'{title}: **#{position}** of {len(rows)} — {display(key,v)}')
        else: lines.append(title+': No recorded score yet.')
    await interaction.response.send_message('\n'.join(lines),ephemeral=True)
@bot.tree.command(description='Browse rankings, including players outside the top 10')
@app_commands.choices(category=[app_commands.Choice(name=title,value=key) for key,(title,_) in META.items()])
@app_commands.guild_only()
async def leaderboard(interaction:discord.Interaction,category:str='packs',page:app_commands.Range[int,1,100000]=1):
    rows=DB.ranked(category); start=(page-1)*10
    lines=[f'{1+sum(r[2]>v for r in rows)}. <@{u}> — {display(category,v)}' for u,n,v in rows[start:start+10]]
    await interaction.response.send_message(f'**{META[category][0]} — Page {page}**\n'+('\n'.join(lines) or 'No players on this page.'),ephemeral=True)
if __name__=='__main__': bot.run(os.environ['DISCORD_TOKEN'],log_handler=None)
