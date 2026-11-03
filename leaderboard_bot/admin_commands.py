"""Moderator-only score overrides. Existing OCR submission rules stay unchanged."""
import logging
import re
from decimal import Decimal, localcontext
import discord
from discord import app_commands
from ocr import SUFFIXES


def parse_score(category, text):
    if category not in ('packs', 'money', 'coins'):
        raise ValueError('Unknown category.')
    text = text.strip()
    if len(text) > 80:
        raise ValueError('Score is too long.')
    # Strict comma grouping; no exponent notation or silently discarded decimals.
    match = re.fullmatch(r'(\$?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?([A-Za-z]*)', text)
    if match is None:
        raise ValueError('Use a nonnegative number, such as 4619 or $26.7Qa.')
    currency, integer, fraction, suffix = match.groups()
    if category != 'money' and (currency or fraction or suffix):
        raise ValueError('Packs and coins must be whole numbers without suffixes.')
    if suffix not in SUFFIXES:
        raise ValueError('Supported suffixes: K, M, B, T, Qa, Qi (case-sensitive).')
    with localcontext() as context:
        context.prec = 100
        value = Decimal(integer.replace(',', '') + (fraction or '')) * 10**SUFFIXES[suffix]
        if value != value.to_integral_value() or not 0 <= value < 10**60:
            raise ValueError('Score must resolve to a whole number below 10^60.')
        return int(value)


def register_admin(bot, store, guild_id, categories, display):
    async def authorized(interaction):
        if interaction.guild_id != guild_id:
            raise app_commands.CheckFailure('Use this command in the configured server.')
        if not interaction.permissions.manage_guild:
            raise app_commands.MissingPermissions(['manage_guild'])
        return True

    async def refresh(interaction, summary):
        # Commit already succeeded: a Discord failure must not be reported as a failed save.
        try:
            await bot.boards()
        except Exception:
            logging.exception('Admin edit saved; leaderboard refresh pending')
            summary += '\nSaved, but the public leaderboard refresh is pending; it will retry automatically.'
        await interaction.followup.send(summary, ephemeral=True)

    @bot.tree.command(name='admin-set', description='Correct one existing player score (Manage Server required)')
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.check(authorized)
    @app_commands.choices(category=[app_commands.Choice(name=title, value=key) for key,(title,_) in categories.items()])
    @app_commands.describe(player='Player whose recorded score needs correction', category='Statistic to change',
                           value='Exact count or money such as $26.7Qa', reason='Why this score needs correction')
    async def admin_set(interaction: discord.Interaction, player: discord.User, category: str,
                        value: app_commands.Range[str, 1, 80], reason: app_commands.Range[str, 1, 300]):
        try:
            parsed = parse_score(category, value)
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            before, after = store.admin_change(interaction.user.id, player.id, reason, category, parsed)
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await refresh(interaction, f'Updated <@{player.id}> — {categories[category][0]}: '
                      f'**{display(category,before[category])} → {display(category,after[category])}**. Audit saved.')

    @bot.tree.command(name='admin-remove', description='Remove a player from all rankings (Manage Server required)')
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.check(authorized)
    @app_commands.describe(player='Player to remove from all three rankings', reason='Why the entry is being removed',
                           confirm='Choose True to confirm removal from all categories')
    async def admin_remove(interaction: discord.Interaction, player: discord.User,
                           reason: app_commands.Range[str, 1, 300], confirm: bool):
        if not confirm:
            await interaction.response.send_message('Cancelled. No scores changed.', ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            store.admin_change(interaction.user.id, player.id, reason)
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True)
            return
        await refresh(interaction, f'Removed <@{player.id}> from all three rankings. Audit saved.')

    async def on_error(interaction, error):
        if isinstance(error, app_commands.MissingPermissions):
            text = 'You need Manage Server permission to use this command.'
        elif isinstance(error, app_commands.CheckFailure):
            text = 'Use this command in the configured server with Manage Server permission.'
        else:
            logging.error('Admin command failed', exc_info=(type(error), error, error.__traceback__))
            text = 'The command encountered an error. Check /rank before retrying; the change may already be saved. Ask the maintainer to check the logs.'
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)

    admin_set.error(on_error)
    admin_remove.error(on_error)
