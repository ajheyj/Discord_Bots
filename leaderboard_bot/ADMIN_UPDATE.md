# Admin correction update — based on commit 7328ea2

## Install on your existing Debian container 205

This archive contains only the new and changed files. Upload them into the matching paths in your GitHub repository, overwriting the previous versions. The archive's leaderboard_bot/ directory belongs under the repository root. Do not nest it inside another leaderboard_bot/ directory. Existing .env, data/, ocr.py, requirements.txt and your installed systemd service are not replaced.

After updating GitHub, run inside container 205:

```sh
systemctl stop leaderboard-bot
cd /opt/Discord_Bots/leaderboard_bot
mkdir -p /root/leaderboard-backups
cp data/leaderboard.sqlite3 /root/leaderboard-backups/leaderboard-before-admin-$(date +%Y%m%d-%H%M%S).sqlite3
cd /opt/Discord_Bots
git pull --ff-only
cd leaderboard_bot
.venv/bin/python -m unittest discover -s tests -v
```

Expect 14 passing tests. If any command fails, stop and inspect the error before proceeding. To restart the previously working bot after an unsuccessful update attempt, restore the old code first as described below. Do not run git reset --hard on a checkout containing changes you want to keep.

After the tests pass:

```sh
chown -R leaderboard:leaderboard /opt/Discord_Bots/leaderboard_bot
chmod 600 /opt/Discord_Bots/leaderboard_bot/.env
systemctl start leaderboard-bot
systemctl status leaderboard-bot --no-pager
journalctl -u leaderboard-bot -n 30 --no-pager
```

No new packages or .env settings are needed. Startup automatically adds the admin_audit table to the existing database without deleting scores, submission audits or leaderboard message IDs. It also syncs the new commands to your configured server. Discord may take a moment to show them; reopen Discord if needed.

## Commands

Both commands require Manage Server permission (Discord's internal name: manage_guild). The bot checks this permission when a command is invoked, as well as setting its default Discord command permissions. Both commands work only in the configured server and return private responses.

- `/admin-set player:@Player category:Packs value:4619 reason:Corrected OCR reading` replaces just that category, including lowering it. Choose the exact category from Discord's dropdown. The player must already have a record. Other categories remain unchanged.
- Money accepts values such as `$26.7Qa`, `1.93Qi`, or full integer values. Comma grouping must be valid. Packs and coins accept whole counts only. Suffixes are case-sensitive and follow the existing game's configured notation. Values must be nonnegative whole units below 10^60.
- `/admin-remove player:@Player reason:Invalid entry confirm:True` removes the player's scores from all three rankings. Setting confirm to False cancels the operation. This does not ban the player or delete their audit history.

A successful edit is committed with its audit row before refreshing public leaderboards. If Discord rejects a display update, the scores remain saved and the usual two-minute refresh retries. An admin receives an explanation. A failed audit insert rolls back the score change.

**Future screenshot submissions can raise a corrected score or re-add a removed player. This includes an OCR job already in the queue.** Wait for pending submissions to finish before making corrections, and moderate invalid future uploads separately. This update does not introduce permanent score caps or player bans. Previously accepted message IDs remain recognized as processed.

## Audit inspection

The database retains admin edits in admin_audit, separate from screenshot submission audits. To inspect the latest changes without installing another package, run from the bot folder:

```sh
.venv/bin/python - <<'PY'
import os, sqlite3
from dotenv import load_dotenv
load_dotenv('.env')
con = sqlite3.connect(os.getenv('DATABASE_PATH', 'data/leaderboard.sqlite3'))
for row in con.execute('SELECT id,time,actor,user,action,category,before_values,after_values,reason FROM admin_audit ORDER BY id DESC LIMIT 20'):
    print(row)
con.close()
PY
```

Discord user IDs identify the moderator and player. Before and after values are JSON; after is null for removal. Reasons are retained in the database and are not reposted to a public channel.

## Verification and rollback

Test a correction on a test player first. Check /rank and the public leaderboard. Try admin-remove with confirm False before testing a confirmed removal. Verify a member without Manage Server permission cannot run either command. Test these actions on disposable test scores; removal has no built-in undo command.

Local verification: all 14 tests pass, including permission checks, cross-server denial, private command responses, correction/removal, transaction rollback when audit writes fail, migration/reopening, number validation and existing core tests. Live Discord command behavior and your Debian installation still require this server-side verification. Docker file copying is updated for the new module, but no Docker build was run.

If needed, stop the service and restore the previous code using Git. The following assumes your checkout has no uncommitted work and that the pre-update version is 7328ea2:

```sh
systemctl stop leaderboard-bot
cd /opt/Discord_Bots
git switch --detach 7328ea2
systemctl start leaderboard-bot
```

The old code ignores the added audit table, so code rollback does not require replacing the database. Scores already corrected stay corrected. To roll back scores too, stop the service and restore the timestamped database backup separately; doing so also discards every submission saved since that backup. Keep the current database as another backup before replacing it. Return to the updated main branch with `git switch main` when ready.

Reference: https://discordpy.readthedocs.io/en/stable/interactions/api.html
