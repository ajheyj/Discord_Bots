# Install, configure and maintain the leaderboard bot

Use this guide for a new installation or the [update procedure](#updating-an-existing-debian-installation) for an existing one. Run only one hosting option. Windows must remain awake; Linux/Proxmox and cloud hosts need to stay online. The bot needs outbound internet to Discord. No inbound port forwarding is needed.

## Discord application and channels

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), sign in, choose New Application, name it and create it.
2. Under Bot, enable **Message Content Intent** and save. This is needed to receive normal message attachments; large/verified applications may require approval. Generate/reset its token and keep it private for `.env` below. Each independently hosted copy should have its own application/token; players using your hosted bot need no token.
3. Under OAuth2 → URL Generator, select `bot` and `applications.commands`. Grant View Channels, Read Message History, Send Messages, Embed Links and Attach Files. Open the generated URL to invite the bot to your server. For automatic pins, grant Pin Messages if available, or pin its messages manually. Administrator permission is unnecessary.
4. Choose an existing submissions text channel and leaderboard text channel, conventionally #leaderboard-submissions and #leaderboard. Use this as the /submit instruction/command channel; players send images in DMs. Old channel uploads remain supported. You may deny ordinary Send Messages/Attach Files while allowing View Channel and Use Application Commands to keep it clean. Optionally restrict leaderboard posting to the bot. Check channel permission overrides.
5. For audit messages, choose an existing private text channel and give the bot View Channel, Send Messages, Embed Links and Attach Files. Give intended moderators View Channel and Read Message History; deny @everyone View Channel if appropriate. The bot does not create or secure channels for you.
6. Enable Discord Settings → Advanced → Developer Mode. Copy the server ID from the server icon, each channel ID from its channel, and optionally a moderator role ID from Server Settings → Roles. Use numeric IDs, not names.

The bot appears offline until the Python program starts.

## Get the project

The repository is [ajheyj/Discord_Bots](https://github.com/ajheyj/Discord_Bots); this bot lives in its `leaderboard_bot` directory. On Windows you can download the repository ZIP and extract it, then open that directory. Keep the complete folder, including `tests/` and `deploy/`. Linux instructions below clone it to `/opt/Discord_Bots`, giving the active bot path `/opt/Discord_Bots/leaderboard_bot`.

## Local configuration

Make a copy of `.env.example` named `.env` in the same directory as `bot.py`. On Windows enable File Explorer → View → Show → File name extensions so the filename is not `.env.txt`. On Linux, after entering the bot folder:

```sh
cp .env.example .env
chmod 600 .env
nano .env
```

For an existing installation, edit the current `.env`; do not replace it with the template. Configure:

```dotenv
DISCORD_TOKEN=your_private_bot_token
GUILD_ID=your_server_id
SUBMISSIONS_CHANNEL_ID=your_submissions_channel_id
LEADERBOARD_CHANNEL_ID=your_leaderboard_channel_id
DATABASE_PATH=data/leaderboard.sqlite3
ADMIN_ROLE_ID=0
AUDIT_CHANNEL_ID=0
HISTORY_LOOKBACK_HOURS=72
# Windows only if Tesseract is not on PATH:
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

| Setting | Meaning |
|---|---|
| `DISCORD_TOKEN` | Private bot token; never commit/share it |
| `GUILD_ID` | Server ID; all channels and the role must belong to this server |
| `SUBMISSIONS_CHANNEL_ID` | Text channel to watch and scan on startup |
| `LEADERBOARD_CHANNEL_ID` | Text channel for the five Top 10 messages |
| `DATABASE_PATH` | SQLite file; default is relative to the bot working directory |
| `ADMIN_ROLE_ID` | Optional exact moderator role; 0/blank/unset uses Manage Server permission |
| `AUDIT_CHANNEL_ID` | Optional existing audit text channel; 0/blank/unset disables channel delivery |
| `HISTORY_LOOKBACK_HOURS` | Startup retry window; default 72, 0 disables, maximum 720 |
| `TESSERACT_CMD` | Optional path to OCR executable, normally needed only on Windows |

Replace placeholder words with actual values. Keep the two optional IDs at 0 until configured. Never use the @everyone role as the admin role. Negative IDs, nonnumeric IDs or an out-of-range history setting prevent startup. Environment variables set by a host/service take precedence over values in `.env` because the bot uses python-dotenv's default behavior. Restart after configuration changes.

In nano, save with Ctrl+O, Enter, then Ctrl+X. Upload only `.env.example` to GitHub. Keep `.env`, `.venv/` and `data/` local; `.gitignore` excludes them from Git, but manual web uploads can bypass that protection. Reset an exposed token immediately; deleting its file does not remove Git history.

## Moderator role and command access

With an actual `ADMIN_ROLE_ID`, the role is required even for administrators and the server owner. Assign it to yourself too. Moderators with that role do not need Manage Server permission. If the role is unset/0, Manage Server is required instead. Role membership is checked for each interaction; a nonexistent role grants nobody access.

After the bot starts, go to **Server Settings → Integrations → your bot → Commands**. For `/admin-set`, `/admin-remove` and `/queue` separately, allow your chosen role and save. In role mode these commands default to administrator-only visibility until Discord permissions grant your role access. Administrators may still see them, but the bot rejects anyone lacking the configured role. Configure only the admin commands so regular players retain `/submit`, `/submission-result`, `/rank` and `/leaderboard`. Moderators also need View Channel and Use Application Commands where they run them.

## Windows

1. Install Python 3.12 from [python.org](https://www.python.org/downloads/), enabling PATH support if offered. Reopen the terminal.
2. Install Tesseract and English language data. The [official Tesseract installation page](https://tesseract-ocr.github.io/tessdoc/Installation.html) links the Windows installer from UB Mannheim. Python packages alone do not install the OCR executable.
3. Set `TESSERACT_CMD` in `.env` if necessary. A common location is `C:\Program Files\Tesseract-OCR\tesseract.exe`.
4. In File Explorer open the extracted `leaderboard_bot` folder, type `cmd` in its address bar and press Enter. Run:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe bot.py
```

Keep the terminal open; Ctrl+C stops the bot. To start again, run the last command from the same folder. The repository does not currently include the earlier optional Windows launcher, so it is not required here.

For automatic startup use Task Scheduler: trigger at logon, Program is the full path to `.venv\Scripts\python.exe`, Arguments is `bot.py`, and Start in is the full bot folder. Configure restart-on-failure if desired and prevent sleep for continuous hosting. Stop any foreground instance before starting the scheduled one.

## Debian/Ubuntu, including Proxmox LXC or VM

Use a guest with network access, not the Proxmox host itself. A starting allocation is 2 vCPU, 2 GB RAM, 512 MB swap and 10 GB disk. Monitor performance. A plain unprivileged LXC running Python needs no Docker nesting. On the Proxmox host, `pct enter 205` opens the existing container's root shell; change 205 for another container. An isolated offline lab network cannot host an online Discord bot.

The following commands assume **root inside the guest**. On a normal non-root Linux account, use `sudo -i` first. Do not run these guest installation commands in the Proxmox host shell.

```sh
apt update
apt install -y git python3 python3-venv tesseract-ocr tesseract-ocr-eng nano ca-certificates
```

For a new installation only:

```sh
git clone https://github.com/ajheyj/Discord_Bots.git /opt/Discord_Bots
cd /opt/Discord_Bots/leaderboard_bot
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

If the repository is already installed, use the update section instead of cloning over it. Configure local `.env` as above, leave `TESSERACT_CMD` commented out on Linux, then test:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python bot.py
```

On Linux expect 123 tests with five optional private-image tests skipped unless you supply their fixtures. Windows also skips the POSIX descendant-process check. Check Discord as below. Stop the foreground process with Ctrl+C before creating/enabling the service.

### Run as a service

Create a service account once; skip useradd if it already exists:

```sh
useradd --system --home /opt/Discord_Bots/leaderboard_bot --shell /usr/sbin/nologin leaderboard
chown -R leaderboard:leaderboard /opt/Discord_Bots/leaderboard_bot
chmod 600 /opt/Discord_Bots/leaderboard_bot/.env
```

Create `/etc/systemd/system/leaderboard-bot.service` with this content:

```ini
[Unit]
Description=Discord OCR Leaderboard Bot
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=leaderboard
WorkingDirectory=/opt/Discord_Bots/leaderboard_bot
ExecStart=/opt/Discord_Bots/leaderboard_bot/.venv/bin/python bot.py
Restart=on-failure
RestartSec=10
UMask=0077

[Install]
WantedBy=multi-user.target
```

This block matches the repository layout. The generic `deploy/leaderboard-bot.service` template uses `/opt/leaderboard-bot`; adjust both its WorkingDirectory and ExecStart if you use it instead. Do not change a working service just because the Markdown was consolidated.

```sh
systemctl daemon-reload
systemctl enable --now leaderboard-bot
systemctl status leaderboard-bot --no-pager
```

Expect `active (running)`. It runs after closing the terminal and starts when the guest boots. In Proxmox, also enable Start at boot for the container if it should boot with the host.

```sh
systemctl restart leaderboard-bot
systemctl stop leaderboard-bot
journalctl -u leaderboard-bot -n 80 --no-pager -l
```

Use `/opt/Discord_Bots/leaderboard_bot/.env` and its `data/` directory for this installation. A Windows `.venv` cannot be reused on Linux; recreate it on the target OS.

## Docker and cloud

Install Docker Engine and the Compose plugin using the [official installation instructions](https://docs.docker.com/engine/install/) for your host. Use an always-on worker/VM with persistent storage, not static hosting or a short-lived serverless function. Run one replica; cloud pricing varies.

In the `leaderboard_bot` directory, create `.env` as above, leave `DATABASE_PATH=data/leaderboard.sqlite3` and `TESSERACT_CMD` unset, then:

```sh
docker compose up -d --build
docker compose logs --tail=50 -f
```

The image runs as a non-root user, includes Tesseract, and stores data in a named volume mounted at `/app/data`. Ctrl+C leaves the log viewer without stopping the bot. `docker compose stop` stops it; `docker compose up -d` starts it; `docker compose down` retains its volume. **Do not use `docker compose down -v`** unless intentionally deleting all stored data.

For managed cloud workers, set secrets as environment variables and mount a writable persistent disk; point DATABASE_PATH to it. Verify redeployments preserve it. This project supplies generic Docker/cloud support, not a deployment to a specific vendor. Keep host security updates enabled.

## Check the installation

- Bot online; five messages appear in the leaderboard channel. Pin them manually if necessary.
- Run `/submit` in the server. Verify its response is private, then send one or two screenshots to the bot in DMs. Check its private result summary and the audit channel. Test a partially readable image: only recognized values should update. Test an unreadable image: the private failure summary should leave all scores unchanged. Test `/submission-result` and blocked-DM handling too.
- `/rank` and `/leaderboard` work for players, including players outside the Top 10.
- A moderator can correct a test player's score with `/admin-set`, including setting it to its existing value with reason `Audit test`. Verify a member without the required role/permission is denied.
- `/admin-remove ... confirm:False` cancels; test confirmed removal only on disposable scores. There is no undo command.
- Admin changes and failure reports appear in the configured audit channel. Existing scores remain intact.

Commands sync to the configured server on startup. If missing, check IDs, invitation scopes and logs, then reopen Discord after waiting briefly. Current automated validation and limits are in [TEST_RESULTS.md](TEST_RESULTS.md); broad Windows/Docker/cloud behavior has not been live-validated by the build tests.

## Startup recovery and audit troubleshooting

Restarting triggers the configurable 72-hour scan described in [README.md](README.md#recovering-failed-images). It retries failed/unprocessed supported images, including offline uploads. It does not revisit already-successful messages. For a fixed OCR issue, install and restart before the original upload falls outside the window. Leave original messages available; older/deleted/inaccessible images need a new upload. No periodic re-scan or manual re-scan slash command is included.

Look for `Scanning submission history` and `History scan finished` in logs. Backlogs can take time after the scan finishes queueing. Verify View Channel and Read Message History in submissions. History API/permission failures retry after 60 seconds; other scan/configuration failures are logged and require fixing/restarting.

Audit delivery uses your existing `AUDIT_CHANNEL_ID`. Admin changes include exact old/new values, moderator and reason. Screenshot failures link to the original message and identify unreadable stats or safe processing-error categories. Queue-stage errors are recorded in service logs; safe terminal-failure reasons go to Discord. Cached images are copied to the audit channel when available and within its upload limit; the original DM link alone is not accessible to moderators. Grant Attach Files there. No channel is created. See [README.md](README.md#audit-channel-and-data) for deduplication, retries and delivery limits. Keep the audit channel private yourself.

If audit messages are missing, confirm the ID, restart to load config, check View Channel/Send Messages/Embed Links there and wait up to 60 seconds. Transient jobs stay queued; completed successes, partial successes and failures produce audit summaries. New public reactions/replies are disabled. Players receive DMs; `/submission-result` is the private fallback when DMs are blocked. Database failure can prevent durable reporting. For a safe configuration check, without displaying the token:

```sh
cd /opt/Discord_Bots/leaderboard_bot
grep -E '^(ADMIN_ROLE_ID|AUDIT_CHANNEL_ID|HISTORY_LOOKBACK_HOURS)=' .env
journalctl -u leaderboard-bot -n 80 --no-pager -l
```

## Private DM submissions

Run `/submit` in the configured server. The response is ephemeral (only the caller sees it); the bot DMs instructions and opens a 24-hour upload session. Use Application Commands and View Channel must be allowed where players run it. No new environment variables are required. Commands sync on startup. Users send one or two image attachments per DM message and receive a private acknowledgment plus result summary. Without an open session, the bot asks them to run /submit first. A session is tied to their Discord ID and the configured server command; it is not Epic ownership verification.

`/submission-result` returns only the requesting user's latest completed snapshot, privately. It is useful when DMs are blocked or delayed. Public boards remain public. Audit summaries and available screenshot copies go only to the configured audit channel, whose permissions you control. The DM prompt and pinned guide explain moderator access.

Startup history recovery also checks DM channels for recorded sessions within the lookback window, including uploads made while offline and before their session expired. Accepted jobs resume independently. Messages outside a session or outside the history window need /submit and a new upload. Successful partial results are completed jobs and are not automatically re-read for missing values.

Old submissions-channel uploads still work and receive DMs for compatibility. To stop new public image posts, use channel permissions to deny Send Messages/Attach Files for players while permitting View Channel and Use Application Commands. Pin the new SCREENSHOT_GUIDE first. This permission change is manual; the bot does not alter channels.

## Player Stats layout and safe migration

The bot reads the username directly below **Player Stats**, plus the visible packs, money, grade coins, shiny cards and playtime. At least one numeric stat must be confidently read; every other unreadable/off-screen stat is left unchanged. The top and scrolled views can be submitted together (one or two images per message, each <=15 MB), but their header names must match exactly. A mismatched pair of readable names rejects both; an unreadable image may be skipped while the other image saves recognized values. Separate DM messages work too.

Discord user ID remains the permanent key. Names change without duplicating scores; all boards display the latest accepted Epic name alongside the Discord mention. Missing/off-screen values retain previous maxima, and never-recorded fields remain unknown. A scrolled view may omit packs. Playtime is optional when off-screen, is stored as seconds and ranked by greatest recorded duration. Numeric changes still retain independent maxima. This does not verify Epic account ownership.

The Player Stats update adds no dependencies beyond the already-installed OpenCV OCR fix. The later durable-queue controls below have safe defaults; existing .env files do not need replacement. Follow the update procedure below, especially its **database backup**. Startup adds nullable shiny/playtime columns and profile/name-history tables, keeps existing scores and public-board IDs, and creates two extra leaderboard messages. This migration requires a matching old database backup for rollback to pre-upgrade code; do not simply switch old code onto the new schema.

Test these values from the supplied new screenshots:

| Field | Expected |
|---|---|
| Username | CROSSBAR_CHRIS |
| Packs | 9,057 (top view) |
| Money | $34.7Qi |
| Grade coins | 986 |
| Shiny cards | 6 |
| Playtime | 03d 09h 41m 30s (scrolled view), stored as 294090 seconds |

Existing successful messages are skipped by the 72-hour recovery even if new fields were previously unavailable. Submit a new screenshot to populate those fields; previously failed recent images are eligible for retry. A new Epic name is adopted using the screenshot message's posting time, not the unverified image capture date. Profiles/history remain attached to one Discord ID; there is no automatic merging between different Discord accounts.

Use `/admin-set` for shiny cards or playtime corrections just like the other categories. Playtime accepts either a duration such as `03d09h41m30s` or integer seconds. The audit channel includes those corrections. An old record with no new metric displays Not recorded until its first value arrives.

## Durable queue configuration

Accepted jobs are now stored in SQLite before private acknowledgment. Images download into a dedicated private disk spool, then one isolated OCR subprocess handles each submission sequentially. Two download workers keep images moving without downloading everything into RAM. Both Tesseract and OpenCV are restricted to one native thread for queued OCR; BLAS threads are also limited. This is not a fixed CPU-percentage cap, and offline OCR commands run separately. Timeouts terminate OCR's process tree on the tested Linux path. Windows tree termination uses taskkill and needs platform verification.

Pending jobs and cached images survive ordinary process/container restarts, including jobs older than 72 hours. The history scan still discovers previously unaccepted messages or retries terminal failures within its window. Already-active/completed jobs are skipped. Resource-rejected historical messages are logged but not accepted; they may need another startup or a new upload when capacity is available. An attachment removed before it finishes caching cannot be recovered from metadata alone. Once cached, OCR can proceed without fetching the original again. Editing an accepted message does not replace its saved attachment IDs; submit a new message to change images.

All settings below are optional; omitting them uses these defaults. Existing local .env files can remain as they are. The complete template stays in `.env.example`, without secrets. Sizes named MB are **MiB** (1,048,576 bytes). Blank numeric settings are invalid; use a number or omit the line.

| Setting | Default | Purpose |
|---|---|---|
| `QUEUE_MAX_PENDING` | 2000 | Maximum active jobs; not a promise to fit all their images |
| `QUEUE_MAX_PER_USER` | 5 | Pending submissions per Discord ID |
| `SPOOL_MAX_MB` | 2048 | Reserved image-storage budget, including retained failed files |
| `SPOOL_MIN_FREE_MB` | 512 | Free filesystem margin, accounting for accepted downloads not yet cached |
| `DOWNLOAD_WORKERS` | 2 | Concurrent download stages; allowed 1–4 |
| `DOWNLOAD_TIMEOUT_SECONDS` | 90 | Whole download stage deadline per attempt, including message refresh |
| `OCR_JOB_TIMEOUT_SECONDS` | 180 | Whole one/two-image OCR subprocess deadline; allowed 5–1800 |
| `JOB_MAX_ATTEMPTS` | 3 | Maximum attempts per download/OCR stage for retryable faults |
| `JOB_RETRY_SECONDS` | 60 | Initial retry delay; later retries back off exponentially |
| `FAILED_IMAGE_RETENTION_HOURS` | 72 | Maximum failed-file retention; 0 deletes on failure; pressure can evict sooner |
| `BACKUP_INTERVAL_HOURS` | 24 | Consistent database backup interval; 0 disables |
| `BACKUP_KEEP` | 7 | Number of automatic database backups to retain |
| `LEADERBOARD_REFRESH_SECONDS` | 30 | Dirty-board batch interval; unchanged boards are not edited |
| `SPOOL_PATH` | beside database, under `spool/` | Optional dedicated image-cache directory |
| `BACKUP_PATH` | beside database, under `backups/` | Optional dedicated backup directory |

With the default DATABASE_PATH, paths are `data/spool` and `data/backups`. Keep both on persistent storage. They must be dedicated separate, non-nested directories and cannot be ancestors of the database. The service account needs ownership/write access, including custom paths outside the project. Do not place unrelated files inside the spool: cleanup removes unreferenced numeric job folders after a DB restore. A database file is required; blank paths and :memory: are rejected. One local instance lock prevents two workers sharing that database.

With audit delivery enabled, successful images are kept until their summary/images reach the audit channel or the retention limit; otherwise successful files are deleted immediately. Failed images may remain up to the retention limit. Any terminal cache can be evicted sooner under storage pressure. Terminal failure clears the pending job but preserves its error/audit. Permanent unreadable inputs do not get wasteful repeated OCR; temporary errors/timeouts have bounded retries. An interrupted attempt retains its count, so repeated restarts do not bypass the attempt limit. Private result delivery retries separately and cannot roll back a committed score. DMs blocked by the user are not retried indefinitely; `/submission-result` privately shows the committed result. Admission errors are private too. The bot sends no new public processing replies/reactions.

**For a 500-member server:** the defaults allow 500 separate one/two-image jobs if their total reservations fit the storage/free-space limits. 1,000 images averaging 2 MiB need about 2,000 MiB; at the 15 MiB maximum they need 15,000 MiB and will exceed the default. Increase spool size only when the guest has enough actual disk. CPU remains one OCR job at a time; a backlog can take hours. If sustained arrivals exceed processing speed, capacity eventually fills and new jobs are explicitly rejected rather than silently accepted. Database/hardware failures still require operator attention.

### Queue status and board updates

`/queue` returns private moderator-only counts by job stage, oldest pending age, reserved image storage, worker state, last backup and last issue. Give your configured admin role command access under Discord Integrations, just like the other admin commands. Regular players keep /rank and /leaderboard. Public boards batch dirty changes every 30 seconds by default and health-check periodically for missing messages. Admin edits still request immediate board refresh.

SQLite now uses WAL with FULL synchronization. **Do not back up a live WAL database by copying only leaderboard.sqlite3:** committed data may still be in its -wal file. Use the SQLite backup API/helper below, or archive the entire stopped data directory including SQLite sidecars and cached images. Keep data local to the worker (not a multi-host/shared-network queue).

## Updating an existing Debian installation

Commit changes to the repository first. Run inside the guest as root, one command at a time. Stop and inspect any failure before continuing:

```sh
systemctl stop leaderboard-bot
cd /opt/Discord_Bots/leaderboard_bot
```

Before pulling new code, make a consistent backup with the existing Python environment. This works before the new helper is installed and includes committed WAL data:

```sh
.venv/bin/python - <<'PYBACKUP'
import os, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv('.env')
source = Path(os.getenv('DATABASE_PATH', 'data/leaderboard.sqlite3')).resolve()
folder = Path('/root/leaderboard-backups')
folder.mkdir(mode=0o700, parents=True, exist_ok=True)
folder.chmod(0o700)
target = folder / ('leaderboard-before-update-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
a = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
b = sqlite3.connect(target)
try:
    a.backup(b)
    assert b.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
finally:
    b.close()
    a.close()
target.chmod(0o600)
print(target)
PYBACKUP
```

Once that prints the backup path without errors, update and test:

```sh
cd /opt/Discord_Bots
git status --short
git rev-parse --short HEAD
git pull --ff-only
cd leaderboard_bot
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Keep the preceding commit ID for rollback. If Git reports uncommitted work or cannot fast-forward, inspect it; do not blindly discard changes. Expected current test result: 123 discovered, 118 pass, 5 private-image tests skipped. Preserve `.env` and `data/`; add any desired new settings to the existing local file, never copy the template over it. Startup migrations preserve existing scores, profiles and audits while adding the durable queue and indexes. Keep the backup made above. On first startup pending jobs resume and the history scan considers recent messages. No old queue files need manual conversion. Always install updated requirements: OpenCV headless/NumPy are required by panel fallback. Then:

```sh
chown -R leaderboard:leaderboard /opt/Discord_Bots/leaderboard_bot
chmod 600 .env
systemctl start leaderboard-bot
systemctl status leaderboard-bot --no-pager
journalctl -u leaderboard-bot -n 80 --no-pager -l
```

Previously accepted pending jobs resume independently of the history window. Newly accepted failed images inside the history window receive private results; successful submissions remain skipped. Code rollback does not undo score changes already saved.

For Windows, stop the foreground/scheduled process, back up data, update project files without replacing `.env`/`data/`, reinstall requirements, test and restart. For Docker, stop/back up, update code and rebuild with `docker compose up -d --build`; preserve the named data volume.

## Backups, restoration and rollback

Automatic backups run every 24 hours by default (and on startup if no recent backup exists), retain seven files, and use SQLite's backup API plus an integrity check. They are stored privately under data/backups by default. They contain scores, queue metadata and audits, **not cached images or .env**. Keep a separate off-host copy and test restoring it. The last backup is visible in /queue; service logs report failures. These copies do not protect against loss of the same host/disk.

For a manual consistent database backup after installing the update, run from the bot folder:

```sh
.venv/bin/python storage_tools.py --destination /root/leaderboard-backups --keep 7
```

On Windows use `.venv\Scripts\python.exe storage_tools.py --destination "C:\PrivateBackups\leaderboard" --keep 7`. The helper reads DATABASE_PATH from local .env (or accepts --database). Its destination must be a separate dedicated directory. It can safely back up the running database. Do not copy only a live .sqlite3 file in WAL mode.

For full queued-image disaster recovery, stop the bot and copy/archive the **entire data directory** (database, -wal/-shm sidecars if present, and spool), plus .env kept privately. Restart after the copy. A database-only restore preserves job records but may need to re-download missing images; deleted originals cannot be recovered if their cached files were not backed up.

Restore only while stopped. Back up current data before replacing it; restoration discards submissions/admin changes made after the backup. For a database-only restore, first stop the bot, preserve the current data folder as another backup, and restore into a fresh data folder at the configured DATABASE_PATH with no stale -wal/-shm files from the replaced database. For full recovery restore the matching entire data folder/volume. Give the service user ownership and restart. New pending messages still inside the startup window may be replayed after restoring an older database.

For Docker, use a POSIX shell for binary archive redirection; older Windows PowerShell can corrupt binary output:

```sh
docker compose stop
docker compose run --rm --no-deps --entrypoint tar bot -czf - -C /app/data . > leaderboard-data-backup.tar.gz
docker compose up -d
```

To restore, stop and make a fresh backup of the existing volume first. Choose a **new, unused** named volume for the restore. Change only the bottom volume definition in compose.yaml (keep the service mount `bot-data:/app/data`):

```yaml
volumes:
  bot-data:
    name: leaderboard-restored-data
```

After confirming that chosen volume name is new/empty, extract the chosen archive into it and start:

```sh
docker compose run --rm --no-deps -T --entrypoint tar bot -xzf - -C /app/data < leaderboard-data-backup.tar.gz
docker compose up -d
```

This leaves the previous stopped volume available for rollback. Do not extract over an existing database: old -wal/-shm sidecars must not be mixed with a replaced .sqlite3 file. Keep the custom volume name in future deployments, and verify restored contents/ownership. The stopped-volume archive includes cached images and SQLite sidecars.

For code rollback in a clean Git checkout: stop the service, enter `/opt/Discord_Bots` and run `git switch --detach PREVIOUS_COMMIT`, replacing the placeholder with the commit recorded before updating. Restart only after checking that version's dependencies/settings. Return with `git switch main` when ready. The new shiny/playtime columns make a direct rollback to older code unsafe: older score inserts assumed the five-column schema. Restore the matching pre-upgrade database backup while stopped if reverting to that code; this discards post-backup submissions and new metrics. Keep the current database as another backup before replacing it. Code-only rollback is not sufficient for this migration. A pre-durable version also ignores pending queue records; do not roll back with pending jobs unless you deliberately pause them and preserve their database/spool for returning to the new version. Do not use a destructive reset to solve an unknown update failure.

## Inspect local admin audit history

From the bot folder, this reads the configured database without printing the token:

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

Moderator/player IDs identify who changed what. Before/after values are JSON, with null after removal. Use a controlled admin correction to fix a record; removal does not block future submissions. Failed messages remain eligible for startup recovery.

## OCR troubleshooting and maintenance

Run an original attachment through OCR without Discord:

```sh
cd /opt/Discord_Bots/leaderboard_bot
.venv/bin/python ocr.py "/path/to/image.png"
```

It prints known numeric values plus the new-layout username, or a failure. Playtime is returned in seconds; off-screen fields are absent. Re-saving/compressing an image can change the result. For the legacy UI, `ocr.py` contains LABELS and the old colon-based extraction. For the new blue UI, `player_panel.py` contains ALIASES and detected header/row/value-box processing. Update SUFFIXES in `ocr.py` only after verifying a notation. New rows are associated geometrically; a colon is not required. A panel moving alone normally needs no edit. Do not weaken confidence/consistency checks just to force one image through; compare known images and unreadable cases. Edit the repository too so reinstallations retain the fix.

| Problem | Checks |
|---|---|
| Bot fails to start | Local .env filename, required values, numeric IDs, dependencies, configuration range and service logs |
| LoginFailure | Reset/copy token privately, edit local .env, restart |
| PrivilegedIntentsRequired / ignored attachments | Message Content Intent in portal, correct IDs and channel access |
| TesseractNotFoundError | Install engine/English data; Windows executable path |
| Missing cv2 or numpy | Install current requirements in the same .venv used by the service |
| Readable image fails or is only partially read | Audit reason, original attachment, new suffix/label/layout, glare/size/contrast; keep it available for startup retry |
| No private response | Run /submit in the configured server; allow DMs from server members; check /submission-result and service logs |
| Result saved but boards delayed | Save succeeded; dirty boards refresh every 30 seconds by default; check destination permissions |
| Admin role denied / command missing | Exact role ID and membership, command-specific integration overrides, configured server and startup sync |
| No history recovery | Startup logs, window, success marker, attachment format/count, message retention and history permissions |
| Scores lost after redeploy | Persistent database/spool paths or volume, and matching backup restoration |
| Queue is not clearing | /queue stage counts/oldest age, storage margin, task errors, permissions and retry deadlines |
| Another instance is using queue | Stop the duplicate process/service; do not delete a lock file to bypass a live lock |
| Valid OCR jobs time out | Inspect audit reasons; tune OCR_JOB_TIMEOUT_SECONDS after testing, especially under CPU quotas |
| PyNaCl/davey voice warnings | This bot uses no voice features; those warnings do not prevent leaderboard operation |

OCR cannot prove account ownership or authenticity, and repeated OCR readings can repeat an error. Money abbreviations cannot reveal hidden game precision. See [README.md](README.md#how-ocr-works) and [TEST_RESULTS.md](TEST_RESULTS.md) before relying on scores for a competition.

## November 15 update checks

After backing up and installing all matching update files (including image_scan.py and leaderboard_guide.py), run the suite: **123 discovered, 118 passed, 5 optional fixtures skipped** on the tested Linux setup. Existing .env values need no change. Restart leaderboard-bot, allow its normal refresh, then confirm one pinned instruction embed appears before the five scoreboards. Pin permission is needed; if denied, pin the bot's guide manually. It reuses existing bot scoreboard slots without deleting posts, so prior scoreboard-message links may now show another category/the guide. Scores are unchanged by that layout migration.

Resend previously completed partial submissions to retry newly readable fields. Each player must use their own Discord account and screenshots; two different players' images do not belong in the same submission. Test /submit, private results and audit screenshot copies. A size discrepancy now validates the image and records its actual cached size without relaxing attachment identity, disk budget or image limits. Pixel and byte failures remain rejected. Whole-image fallback improves varied placement, but uncertainty still leaves a field unchanged; it does not promise every photograph will read.


## Photo recovery and audit-thread update
Back up the database using the backup steps above, then install this patch after the image-recovery/guide update. Keep the existing `.env`; no new settings or dependencies are required.

In the audit channel, allow the bot **View Channel**, **Read Message History**, **Create Public Threads**, **Send Messages in Threads**, **Embed Links**, and **Attach Files**. **Manage Threads** is needed if moderators lock threads that the bot must reopen. Keep access to the parent audit channel limited to moderators. Missing permissions leave audit deliveries pending.

Upload the ZIP's `leaderboard_bot/` files into their matching GitHub paths. Then:

```bash
cd /opt/Discord_Bots
git pull --ff-only
systemctl restart leaderboard-bot
```

The two threads are created when their first matching results are delivered. Check each with a successful submission and a failed/partial submission. Old audit posts stay where they are. Screenshot limits and cache retention still apply.

This package includes automatic failed-DM review. Failed accepted submissions within `HISTORY_LOOKBACK_HOURS` (72 by default) are automatically retried once per reader revision at startup, including after session expiry. Partial successes are not automatically replayed. Deleted/inaccessible originals cannot be recovered. If this photo already produced a partial success on your server, it must be resubmitted to recover its missing fields.
