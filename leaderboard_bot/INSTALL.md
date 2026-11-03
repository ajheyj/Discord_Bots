# Install, configure and maintain the leaderboard bot

Use this guide for a new installation or the [update procedure](#updating-an-existing-debian-installation) for an existing one. Run only one hosting option. Windows must remain awake; Linux/Proxmox and cloud hosts need to stay online. The bot needs outbound internet to Discord. No inbound port forwarding is needed.

## Discord application and channels

1. Open the [Discord Developer Portal](https://discord.com/developers/applications), sign in, choose New Application, name it and create it.
2. Under Bot, enable **Message Content Intent** and save. This is needed to receive normal message attachments; large/verified applications may require approval. Generate/reset its token and keep it private for `.env` below. Each independently hosted copy should have its own application/token; players using your hosted bot need no token.
3. Under OAuth2 → URL Generator, select `bot` and `applications.commands`. Grant View Channels, Read Message History, Send Messages, Embed Links and Add Reactions. Open the generated URL to invite the bot to your server. For automatic pins, grant Pin Messages if available, or pin its messages manually. Administrator permission is unnecessary.
4. Choose an existing submissions text channel and leaderboard text channel, conventionally #leaderboard-submissions and #leaderboard. Let players attach files in submissions. Optionally restrict leaderboard posting to the bot. Check channel permission overrides.
5. For audit messages, choose an existing private text channel and give the bot View Channel, Send Messages and Embed Links. Give intended moderators View Channel and Read Message History; deny @everyone View Channel if appropriate. The bot does not create or secure channels for you.
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
| `LEADERBOARD_CHANNEL_ID` | Text channel for the three Top 10 messages |
| `DATABASE_PATH` | SQLite file; default is relative to the bot working directory |
| `ADMIN_ROLE_ID` | Optional exact moderator role; 0/blank/unset uses Manage Server permission |
| `AUDIT_CHANNEL_ID` | Optional existing audit text channel; 0/blank/unset disables channel delivery |
| `HISTORY_LOOKBACK_HOURS` | Startup retry window; default 72, 0 disables, maximum 720 |
| `TESSERACT_CMD` | Optional path to OCR executable, normally needed only on Windows |

Replace placeholder words with actual values. Keep the two optional IDs at 0 until configured. Never use the @everyone role as the admin role. Negative IDs, nonnumeric IDs or an out-of-range history setting prevent startup. Environment variables set by a host/service take precedence over values in `.env` because the bot uses python-dotenv's default behavior. Restart after configuration changes.

In nano, save with Ctrl+O, Enter, then Ctrl+X. Upload only `.env.example` to GitHub. Keep `.env`, `.venv/` and `data/` local; `.gitignore` excludes them from Git, but manual web uploads can bypass that protection. Reset an exposed token immediately; deleting its file does not remove Git history.

## Moderator role and command access

With an actual `ADMIN_ROLE_ID`, the role is required even for administrators and the server owner. Assign it to yourself too. Moderators with that role do not need Manage Server permission. If the role is unset/0, Manage Server is required instead. Role membership is checked for each interaction; a nonexistent role grants nobody access.

After the bot starts, go to **Server Settings → Integrations → your bot → Commands**. For `/admin-set` and `/admin-remove` separately, allow your chosen role and save. In role mode these commands default to administrator-only visibility until Discord permissions grant your role access. Administrators may still see them, but the bot rejects anyone lacking the configured role. Configure only the admin commands so regular players retain `/rank` and `/leaderboard`. Moderators also need View Channel and Use Application Commands where they run them.

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

Expect 52 tests with three optional private-image tests skipped unless you supply their fixtures. Check Discord as below. Stop the foreground process with Ctrl+C before creating/enabling the service.

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

- Bot online; three messages appear in the leaderboard channel. Pin them manually if necessary.
- Submit one clear screenshot. Expect ⏳ then ✅; compare all three stored values with the image. Test a bad image and confirm ❌ without a score update.
- `/rank` and `/leaderboard` work for players, including players outside the Top 10.
- A moderator can correct a test player's score with `/admin-set`, including setting it to its existing value with reason `Audit test`. Verify a member without the required role/permission is denied.
- `/admin-remove ... confirm:False` cancels; test confirmed removal only on disposable scores. There is no undo command.
- Admin changes and failure reports appear in the configured audit channel. Existing scores remain intact.

Commands sync to the configured server on startup. If missing, check IDs, invitation scopes and logs, then reopen Discord after waiting briefly. Current automated validation and limits are in [TEST_RESULTS.md](TEST_RESULTS.md); broad Windows/Docker/cloud behavior has not been live-validated by the build tests.

## Startup recovery and audit troubleshooting

Restarting triggers the configurable 72-hour scan described in [README.md](README.md#recovering-failed-images). It retries failed/unprocessed supported images, including offline uploads. It does not revisit already-successful messages. For a fixed OCR issue, install and restart before the original upload falls outside the window. Leave original messages available; older/deleted/inaccessible images need a new upload. No periodic re-scan or manual re-scan slash command is included.

Look for `Scanning submission history` and `History scan finished` in logs. Backlogs can take time after the scan finishes queueing. Verify View Channel and Read Message History in submissions. History API/permission failures retry after 60 seconds; other scan/configuration failures are logged and require fixing/restarting.

Audit delivery uses your existing `AUDIT_CHANNEL_ID`. Admin changes include exact old/new values, moderator and reason. Screenshot failures link to the original message and identify unreadable stats or safe processing-error categories. Raw stack traces stay in service logs. No images are archived/reuploaded and no channel is created. See [README.md](README.md#audit-channel-and-data) for deduplication, retries and delivery limits. Keep the audit channel private yourself.

If audit messages are missing, confirm the ID, restart to load config, check View Channel/Send Messages/Embed Links there and wait up to 60 seconds. Successful screenshots do not create audit-channel messages. Same-message/same-reason failures are reported once; do not expect a duplicate every restart. Database failure can prevent durable reporting. For a safe configuration check, without displaying the token:

```sh
cd /opt/Discord_Bots/leaderboard_bot
grep -E '^(ADMIN_ROLE_ID|AUDIT_CHANNEL_ID|HISTORY_LOOKBACK_HOURS)=' .env
journalctl -u leaderboard-bot -n 80 --no-pager -l
```

## Updating an existing Debian installation

Commit changes to the repository first. Run inside the guest as root, one command at a time. Stop and inspect any failure before continuing:

```sh
systemctl stop leaderboard-bot
mkdir -p /root/leaderboard-backups
cp /opt/Discord_Bots/leaderboard_bot/data/leaderboard.sqlite3 /root/leaderboard-backups/leaderboard-$(date +%Y%m%d-%H%M%S).sqlite3
cd /opt/Discord_Bots
git status --short
git rev-parse --short HEAD
git pull --ff-only
cd leaderboard_bot
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Keep the preceding commit ID for rollback. If Git reports uncommitted work or cannot fast-forward, inspect it; do not blindly discard changes. Expected current test result: 52 discovered, 49 pass, 3 private-image tests skipped. Preserve `.env` and `data/`; add any desired new settings to the existing local file, never copy the template over it. The startup migrations add required audit tables without deleting existing records. Always install updated requirements: OpenCV headless/NumPy are required by panel fallback. Then:

```sh
chown -R leaderboard:leaderboard /opt/Discord_Bots/leaderboard_bot
chmod 600 .env
systemctl start leaderboard-bot
systemctl status leaderboard-bot --no-pager
journalctl -u leaderboard-bot -n 80 --no-pager -l
```

Newly accepted failed images in the window update their original reactions; successful submissions remain skipped. Code rollback does not undo score changes already saved.

For Windows, stop the foreground/scheduled process, back up data, update project files without replacing `.env`/`data/`, reinstall requirements, test and restart. For Docker, stop/back up, update code and rebuild with `docker compose up -d --build`; preserve the named data volume.

## Backups, restoration and rollback

Automatic backups are still planned. Stop the bot before copying the SQLite file. On Windows copy `data\leaderboard.sqlite3`; on this Linux installation copy `/opt/Discord_Bots/leaderboard_bot/data/leaderboard.sqlite3`. Keep a private copy of `.env` separately. Restart after copying. Keep another backup outside the container/host and test restoration.

Restore only while stopped. Back up current data before replacing it; restoration discards submissions/admin changes made after the backup. Restore to the configured DATABASE_PATH, give the service user ownership and restart. New pending messages still inside the startup window may be replayed after restoring an older database.

For Docker, use a POSIX shell for binary archive redirection; older Windows PowerShell can corrupt binary output:

```sh
docker compose stop
docker compose run --rm --no-deps --entrypoint tar bot -czf - -C /app/data . > leaderboard-data-backup.tar.gz
docker compose up -d
```

Restore a chosen archive while stopped:

```sh
docker compose stop
docker compose run --rm --no-deps -T --entrypoint tar bot -xzf - -C /app/data < leaderboard-data-backup.tar.gz
docker compose up -d
```

Back up existing volume data before restoration. If changing archive layouts/versions, verify restored contents before starting; extracting overlays files rather than deleting unrelated files.

For code rollback in a clean Git checkout: stop the service, enter `/opt/Discord_Bots` and run `git switch --detach PREVIOUS_COMMIT`, replacing the placeholder with the commit recorded before updating. Restart only after checking that version's dependencies/settings. Return with `git switch main` when ready. Earlier versions ignore the extra audit tables; saved score corrections/recoveries remain unless you separately restore data. Do not use a destructive reset to solve an unknown update failure.

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

It prints the three integer values or a failure. Re-saving/compressing an image can change the result. In `ocr.py`, update LABELS for renamed labels, SUFFIXES only after verifying a new notation, or the extraction/panel preprocessing for layout/font/color changes. Current extraction expects label/colon/value on the same OCR line. A panel moving alone normally needs no edit. Do not weaken confidence/consistency checks just to force one image through; compare known images and unreadable cases. Edit the repository too so reinstallations retain the fix.

| Problem | Checks |
|---|---|
| Bot fails to start | Local .env filename, required values, numeric IDs, dependencies, configuration range and service logs |
| LoginFailure | Reset/copy token privately, edit local .env, restart |
| PrivilegedIntentsRequired / ignored attachments | Message Content Intent in portal, correct IDs and channel access |
| TesseractNotFoundError | Install engine/English data; Windows executable path |
| Missing cv2 or numpy | Install current requirements in the same .venv used by the service |
| Readable image gets ❌ | Audit reason, original attachment, new suffix/label/layout, glare/size/contrast; keep it available for startup retry |
| No reactions | Add Reactions, Read Message History and channel overrides |
| ✅ but boards delayed | Save succeeded; refresh retries every two minutes; check destination permissions |
| Admin role denied / command missing | Exact role ID and membership, command-specific integration overrides, configured server and startup sync |
| No history recovery | Startup logs, window, success marker, attachment format/count, message retention and history permissions |
| Scores lost after redeploy | Persistent database path/volume and backup restoration |
| PyNaCl/davey voice warnings | This bot uses no voice features; those warnings do not prevent leaderboard operation |

OCR cannot prove account ownership or authenticity, and repeated OCR readings can repeat an error. Money abbreviations cannot reveal hidden game precision. See [README.md](README.md#how-ocr-works) and [TEST_RESULTS.md](TEST_RESULTS.md) before relying on scores for a competition.
