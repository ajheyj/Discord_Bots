import asyncio,logging,os,time
from decimal import Decimal
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from ocr import extract,OCRFailure,SUFFIXES,merge_screenshots
from store import Store
from admin_commands import register_admin
from audit_channel import AuditChannel
from submission_replay import SubmissionReplay
from queue_config import QueueConfig
load_dotenv()
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
GUILD=int(os.environ['GUILD_ID']); SUB=int(os.environ['SUBMISSIONS_CHANNEL_ID']); BOARD=int(os.environ['LEADERBOARD_CHANNEL_ID'])
ADMIN_ROLE=int(os.getenv('ADMIN_ROLE_ID') or '0'); AUDIT_CHANNEL=int(os.getenv('AUDIT_CHANNEL_ID') or '0')
if ADMIN_ROLE < 0 or AUDIT_CHANNEL < 0 or ADMIN_ROLE == GUILD:
    raise ValueError('Use valid role/channel IDs; @everyone cannot be the admin role.')
HISTORY_HOURS=int(os.getenv('HISTORY_LOOKBACK_HOURS') or '72')
DB=Store(os.getenv('DATABASE_PATH','data/leaderboard.sqlite3'))
META={'packs':('📦 Packs Opened',0xE5B83B),'money':('💰 Money Earned',0x2ECC71),'coins':('🪙 Grade Coins',0x9B59B6),'shiny':('✨ Shiny Cards',0x3498DB),'playtime':('⏱️ Total Playtime',0xE67E22)}
def display(key,value):
    if value is None:return 'Not recorded'
    if key=='playtime':
        days,seconds=divmod(value,86400);hours,seconds=divmod(seconds,3600);minutes,seconds=divmod(seconds,60)
        return f'{days:02d}d {hours:02d}h {minutes:02d}m {seconds:02d}s'
    if key!='money': return f'{value:,}'
    for suffix,power in reversed(list(SUFFIXES.items())):
        if value>=10**power:
            return '$'+format(Decimal(value)/Decimal(10**power),'.3f').rstrip('0').rstrip('.')+suffix
    return '$0'
def player_label(user,name):
    return f'{discord.utils.escape_markdown(discord.utils.escape_mentions(name))} (<@{user}>)'

class Bot(discord.Client):
    def __init__(self):
        intents=discord.Intents.default(); intents.message_content=True
        super().__init__(intents=intents,allowed_mentions=discord.AllowedMentions.none())
        self.tree=app_commands.CommandTree(self); self.lock=asyncio.Lock()
        self.audit_channel_id=AUDIT_CHANNEL
        self.config=QueueConfig.from_env(DB.path)
        self.submissions=SubmissionReplay(self,DB,GUILD,SUB,hours=HISTORY_HOURS,config=self.config)
        self.boards_dirty=True;self.board_revision=0;self.last_board_check=0
    async def setup_hook(self):
        self.tree.copy_global_to(guild=discord.Object(id=GUILD))
        await self.tree.sync(guild=discord.Object(id=GUILD))
        self.submissions.pipeline.start()
        self.refresh.change_interval(seconds=self.config.board_interval)
        self.refresh.start();self.audit_refresh.start()
        self.history_task=asyncio.create_task(self.submissions.run())
    async def reaction(self,msg,emoji,remove=False):
        try:
            if remove: await msg.remove_reaction(emoji,self.user)
            else: await msg.add_reaction(emoji)
        except discord.HTTPException: logging.warning('Reaction failed for message %s',msg.id)
    async def on_message(self,msg):
        if not msg.author.bot and msg.guild is None and msg.attachments and not self.submissions.eligible(msg):
            await self.submissions.private_notice(msg,'Run /submit in the leaderboard server to open a 24-hour private upload session, then send your screenshots here.')
            return
        await self.submissions.enqueue(msg)

    def mark_scores_changed(self):
        self.board_revision+=1;self.boards_dirty=True

    async def close(self):
        task=getattr(self,'history_task',None)
        if task is not None:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
        self.refresh.cancel();self.audit_refresh.cancel()
        await self.submissions.pipeline.close()
        await super().close()

    async def boards(self):
        async with self.lock:
            channel=await self.fetch_channel(BOARD)
            if channel.guild.id!=GUILD: raise ValueError('Leaderboard channel belongs to another server')
            from leaderboard_guide import ensure_guide
            await ensure_guide(self,DB,channel,META)
            for key,(title,color) in META.items():
                all_rows=DB.ranked(key); rows=all_rows[:10]
                lines=[f'**{1+sum(r[2]>v for r in all_rows)}.** {player_label(u,n)} — **{display(key,v)}**' for u,n,v in rows]
                embed=discord.Embed(title=title+' — Top 10',description='\n'.join(lines) or 'No submissions yet.',color=color)
                embed.set_footer(text='All-time personal bests • /rank • /leaderboard')
                mid=DB.board(key); message=None
                if mid:
                    try: message=await channel.fetch_message(mid)
                    except discord.NotFound: pass
                if message:
                    old=message.embeds[0] if message.embeds else None
                    if old is None or old.title!=embed.title or old.description!=embed.description or old.color!=embed.color or old.footer.text!=embed.footer.text:
                        await message.edit(embed=embed)
                else:
                    message=await channel.send(embed=embed); DB.save_board(key,message.id)
                if not message.pinned:
                    try: await message.pin(reason='Leaderboard')
                    except discord.Forbidden: logging.warning('Pin permission missing; manually pin leaderboard messages')
    @tasks.loop(seconds=60)
    async def audit_refresh(self):
        try: await audit_log.flush()
        except Exception: logging.exception('Audit channel delivery pending; will retry')
    @audit_refresh.before_loop
    async def before_audit_refresh(self): await self.wait_until_ready()
    @tasks.loop(seconds=30)
    async def refresh(self):
        if not self.boards_dirty and time.monotonic()-self.last_board_check<300:return
        revision=self.board_revision
        try:
            await self.boards();self.last_board_check=time.monotonic()
            if revision==self.board_revision:self.boards_dirty=False
        except Exception:logging.exception('Leaderboard refresh failed')
    @refresh.before_loop
    async def before_refresh(self): await self.wait_until_ready()
bot=Bot()
from dm_submissions import register_submissions
register_submissions(bot,DB,GUILD)
@bot.tree.command(description='View your personal standings across all tracked statistics')
@app_commands.guild_only()
async def rank(interaction:discord.Interaction):
    epic=DB.identity(interaction.user.id)
    lines=['**Player: '+discord.utils.escape_markdown(discord.utils.escape_mentions(epic))+'**'] if epic else []
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
    lines=[f'{1+sum(r[2]>v for r in rows)}. {player_label(u,n)} — {display(category,v)}' for u,n,v in rows[start:start+10]]
    await interaction.response.send_message(f'**{META[category][0]} — Page {page}**\n'+('\n'.join(lines) or 'No players on this page.'),ephemeral=True)
audit_log=AuditChannel(bot, DB, GUILD, AUDIT_CHANNEL, META, display)
register_admin(bot, DB, GUILD, META, display, role_id=ADMIN_ROLE,
               audit_channel=audit_log if AUDIT_CHANNEL else None,queue_status=bot.submissions.pipeline.status)

if __name__=='__main__': bot.run(os.environ['DISCORD_TOKEN'],log_handler=None)
