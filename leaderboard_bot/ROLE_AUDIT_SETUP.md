# Moderator role and audit channel configuration

This update adds two optional local .env settings. It never creates Discord channels or roles. Choose an existing role and an existing private server text channel, or create them yourself in Discord if desired.

```dotenv
ADMIN_ROLE_ID=your_existing_moderator_role_id
AUDIT_CHANNEL_ID=your_existing_audit_text_channel_id
```

Replace these examples with actual numeric IDs, not names. With Developer Mode enabled, right-click the role in Server Settings → Roles to copy its ID; right-click the channel to copy its ID. Keep the other .env settings, including the token, unchanged. Do not upload .env to GitHub.

## Role behavior

With ADMIN_ROLE_ID configured, /admin-set and /admin-remove require that exact role. Manage Server, Administrator and server ownership do not bypass the bot's role check: assign the role to yourself too. Role changes are evaluated on each new interaction using Discord's member data. /rank, /leaderboard and screenshot submissions remain available as before. Setting the role ID to the server's @everyone role is rejected.

If ADMIN_ROLE_ID is missing, empty or 0, the previous Manage Server requirement remains for backward compatibility. An invalid nonnumeric ID prevents startup instead of silently changing the policy. A nonexistent role grants nobody access.

### Make the commands visible to your role

After restarting with the new configuration, open Discord **Server Settings → Integrations → your bot → Commands**. For each of /admin-set and /admin-remove, add the configured moderator role as an allowed role and save. Configure the two admin commands individually so you do not restrict /rank and /leaderboard for regular players. Your moderators also need View Channel and Use Application Commands in the channel where they run the command.

The commands default to administrator-only visibility in role mode until you grant your chosen role access in Discord. Discord may still show administrators a command, but the bot rejects execution if they lack the configured role. The runtime check remains effective even if Discord's command permissions are broadened accidentally. Moderators do not need Manage Server when the role setting is configured.

Discord guidance: https://support-apps.discord.com/hc/en-us/articles/26501869403159-Command-Permissions

## Audit channel behavior

Set AUDIT_CHANNEL_ID to an existing text channel in the same server. Give the bot View Channel, Send Messages and Embed Links there. Give your intended moderators View Channel and Read Message History. Deny @everyone View Channel if the channel should be private. The bot does not change these permissions. Check them yourself before enabling audit delivery.

Each successful admin correction/removal posts an embed with moderator/player mentions and IDs, UTC timestamp, action, exact old/new values, reason and database audit ID. Mention notifications are disabled. These are **admin action logs**; normal screenshot submissions retain their existing SQLite audit and do not create channel messages in this update. Failed or cancelled admin commands do not post edit logs because no change occurred.

Logs are queued in the same database transaction as the score change and retried every 60 seconds after connection/startup. Bad channel permissions or Discord outages do not undo a saved correction. The private command reply explains pending delivery, and the service logs the error. A batch sends up to 20 queued messages per flush. Successful deliveries are marked in SQLite and are not normally resent. A crash or ambiguous network failure between Discord accepting a message and the delivery marker being saved can cause a duplicate; its audit ID identifies it. Deleting a delivered Discord message does not automatically recreate it.

Set AUDIT_CHANNEL_ID to 0, leave it blank, or omit it to disable delivery. Admin edits still have database audit records. Edits made with this update while delivery is disabled remain queued and will be sent if you enable it later. Edits recorded before this update are preserved in the database but are not automatically reposted. Changing the configured channel sends pending logs there; previously delivered messages stay where they were sent. This feature provides an audit trail, not tamper-proof storage.

## Update your running Debian container 205

Upload this ZIP's contents into the matching leaderboard_bot/ directory in GitHub, replacing matching files. Keep tests/test_role_audit.py inside tests/. Do not nest another leaderboard_bot/ directory. Then in container 205:

```sh
systemctl stop leaderboard-bot
mkdir -p /root/leaderboard-backups
cp /opt/Discord_Bots/leaderboard_bot/data/leaderboard.sqlite3 /root/leaderboard-backups/leaderboard-$(date +%Y%m%d-%H%M%S).sqlite3
cd /opt/Discord_Bots
git pull --ff-only
cd leaderboard_bot
.venv/bin/python -m unittest discover -s tests -v
```

Expect **23 tests … OK** when both the previous admin update and this update are installed. If any command fails, stop and inspect it before continuing. No new Python dependencies are needed. Add the two real IDs to your LOCAL .env using:

```sh
nano .env
```

Then:

```sh
chown -R leaderboard:leaderboard /opt/Discord_Bots/leaderboard_bot
chmod 600 .env
systemctl start leaderboard-bot
systemctl status leaderboard-bot --no-pager
journalctl -u leaderboard-bot -n 30 --no-pager
```

Configure Discord's command permissions as described above. Test on a disposable player score: a member with the role should be able to correct it; a member without it must be denied. Confirm the audit embed appears in your existing channel. These changes preserve existing score, screenshot audit and leaderboard message records. New database tables are added automatically.

## Validation and limits

23 automated tests pass locally: prior 14 tests plus role checks, denial of administrators without the role, wrong-server denial, disabled-by-default command visibility in role mode, audit fields and suppressed pings, durable retry after restart, rejection of wrong-server/non-text audit targets, removal logging, save behavior during delivery failures, cancellation/invalid input, transaction rollback if queue insertion fails, and migration without replaying old audit logs. Discord connection/setup, role permissions and live delivery still require your server-side checks. Docker copying includes the new module but a Docker build was not tested.

Role and audit settings are read on startup; restart after changing .env. For code rollback, stop the service and return to the previous Git commit (ce6b526 for this update's source); the old code ignores the new delivery table. Back up current data before replacing a database. Corrections/removals still do not prevent future or pending screenshots from raising scores or re-adding players.
