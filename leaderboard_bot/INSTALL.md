# Install and run the Discord screenshot leaderboard

You do not need to have coded before. Choose **one** hosting option below. Windows runs while your PC is awake. A Linux VM or cloud server can stay online. Proxmox hosts a Linux VM; do not install this bot on the Proxmox host itself. Cloud hosting needs an always-running worker and persistent storage, not a static website or short-lived serverless function.

## 1. Unzip and find the bot folder

Extract screenshot-leaderboard-bot.zip. Open the leaderboard-bot folder. You should see bot.py, requirements.txt, INSTALL.md and .env.example. Keep this folder in one place. Commands below must run inside it.

## 2. Make your Discord application

1. Open https://discord.com/developers/applications and sign in. Choose **New Application**, give it a name, and create it.
2. Open **Bot**. If required, create the bot user. Under privileged gateway intents, enable **Message Content Intent**. This is needed to receive screenshot attachments in normal server messages. Large/verified applications may need Discord approval for this intent.
3. Use the token controls to obtain/reset the bot token. Store it privately in the .env file in step 4. Never paste it into Discord, upload it, or share it with anyone. If exposed, reset it immediately and replace it locally.
4. In **OAuth2 → URL Generator**, select `bot` and `applications.commands`. Grant View Channels, Read Message History, Send Messages, Embed Links and Add Reactions. Use the generated link to add the bot to your server. You need permission to manage that server.
5. For automatic pins, give the bot the channel permission Discord currently labels **Pin Messages** (or Manage Messages where applicable). If you prefer, pin its three messages yourself. Administrator permission is unnecessary.

## 3. Create and identify your channels

Create #leaderboard-submissions and #leaderboard. Allow members to attach files in submissions. In #leaderboard, optionally deny members Send Messages while allowing the bot to send messages and embeds. Check channel overrides: they can block permissions granted during the invitation.

In Discord Settings → Advanced, enable **Developer Mode**. Right-click your server icon → Copy Server ID. Right-click each channel → Copy Channel ID. These are long numbers, not channel names. Save the three IDs for step 4.

## 4. Configure the bot

Copy `.env.example` and rename the copy **.env**. On Windows, enable File Explorer → View → Show → File name extensions, so you do not accidentally create `.env.txt`. Open .env in Notepad or a text editor and replace:

```dotenv
DISCORD_TOKEN=your_private_token
GUILD_ID=your_server_id
SUBMISSIONS_CHANNEL_ID=your_submission_channel_id
LEADERBOARD_CHANNEL_ID=your_leaderboard_channel_id
DATABASE_PATH=data/leaderboard.sqlite3
```

Use the exact copied IDs. No angle brackets or extra words. Leave DATABASE_PATH as shown unless you understand persistent storage. All three IDs must belong to the intended server. This package supports one server per running bot.

## 5A. Windows

1. Install Python **3.12** from https://www.python.org/downloads/ . Enable the installer option to add Python to PATH if offered. Reopen your terminal after installation.
2. Install Tesseract with English data. The official Tesseract installation page links the Windows installer maintained by UB Mannheim: https://tesseract-ocr.github.io/tessdoc/Installation.html . Follow that link to its Windows installer. Python packages alone do not install the OCR engine.
3. In .env, remove the # before TESSERACT_CMD and set it to your installed executable. A common path is:

```dotenv
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

4. Open the extracted leaderboard-bot folder in File Explorer. Click its address bar, type `cmd`, and press Enter. Run these commands one at a time:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe bot.py
```

Keep the terminal open. Ctrl+C stops the bot. Later, double-click deploy\start-windows.cmd to start it again. Do not run a second copy while the first is running. For automatic startup, use Windows Task Scheduler: create a task triggered at logon, set Program to the full path of `.venv\Scripts\python.exe`, Arguments to `bot.py`, and Start in to the full bot folder. Disable sleep if this PC must host continuously. Choose restart-on-failure settings if desired.

## 5B. Linux (Ubuntu/Debian), including a Proxmox VM

For Proxmox, create an Ubuntu or Debian VM with network access first. A starting allocation is 2 vCPU, 2 GB RAM and 10 GB disk; monitor OCR performance and increase resources if needed. Install within the VM, using its terminal or SSH. The bot needs outbound internet to Discord while running; an isolated/offline ICS VM will not work for this task. No inbound port forwarding is required.

Copy the unzipped bot folder to your Linux user's home directory. Open a terminal and use `cd` to enter that folder (for example `cd ~/leaderboard-bot`). Then:

```sh
sudo apt update
sudo apt install -y python3 python3-venv tesseract-ocr tesseract-ocr-eng
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python bot.py
```

Leave TESSERACT_CMD commented out on Linux. Ctrl+C stops the foreground test. To keep it running after you log out and restart it after boot, install the provided service:

```sh
sudo useradd --system --home /opt/leaderboard-bot --shell /usr/sbin/nologin leaderboard
sudo mkdir -p /opt/leaderboard-bot
sudo cp -a . /opt/leaderboard-bot/
sudo rm -rf /opt/leaderboard-bot/.venv
sudo python3 -m venv /opt/leaderboard-bot/.venv
sudo /opt/leaderboard-bot/.venv/bin/python -m pip install -r /opt/leaderboard-bot/requirements.txt
sudo chown -R leaderboard:leaderboard /opt/leaderboard-bot
sudo chmod 600 /opt/leaderboard-bot/.env
sudo cp deploy/leaderboard-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now leaderboard-bot
sudo systemctl status leaderboard-bot
```

If the user already exists, skip useradd. Ensure the foreground bot is stopped before starting the service. Commands to manage it:

```sh
sudo journalctl -u leaderboard-bot -n 50 --no-pager
sudo systemctl restart leaderboard-bot
sudo systemctl stop leaderboard-bot
```

The active service uses /opt/leaderboard-bot/.env and data/, not your original extracted folder. Change that copy when updating settings. A copied Windows .venv cannot run on Linux; the commands recreate it.

## 5C. Docker / cloud

Use a Linux cloud VM or local machine with Docker Engine and the Compose plugin. Install Docker by following https://docs.docker.com/engine/install/ for that operating system. Cloud servers cost money while allocated; pricing and plans vary. Keep the VM's security updates enabled.

Copy this folder to the machine, create .env using step 4, then run inside the folder:

```sh
docker compose up -d --build
docker compose logs --tail=50 -f
```

Ctrl+C exits the log viewer, not the bot. `docker compose stop` stops the bot; `docker compose up -d` starts it again. `docker compose down` removes the container while retaining the database volume. **Do not run `docker compose down -v`** unless intentionally deleting all stored scores.

The included Docker image runs as a non-root user, includes Tesseract and uses a persistent named volume at /app/data. Leave DATABASE_PATH=data/leaderboard.sqlite3 and TESSERACT_CMD unset. Run one replica. On a managed cloud worker, set the same secrets as environment variables, provide a persistent writable disk, and set DATABASE_PATH to a file on that disk. Do not assume the container filesystem persists when a provider redeploys it. This is a generic Docker/cloud version, not a preconfigured deployment to a specific vendor.

## 6. Test in Discord

Wait for the bot to appear online. In #leaderboard, expect three messages. Pin them manually if the bot cannot. Upload one screenshot to #leaderboard-submissions. Expect ⏳, then ✅ or ❌. Try /rank and /leaderboard. With a successful submission, confirm that all displayed values match the image before inviting players. Test an unreadable image and confirm it gets ❌ without changing the scores.

The commands are synced to the configured server when the bot starts. If missing, check the server ID, invitation scopes and logs; restart Discord after waiting briefly. On startup the bot retries failed/unprocessed supported image messages posted in the previous 72 hours. Give it View Channel and Read Message History in submissions. It skips successful message IDs and does not reprocess edits to successful submissions. Older, deleted or inaccessible messages need a new upload. See HISTORY_REPLAY_SETUP.md.

## 7. Backups and maintenance

Stop the bot before copying its SQLite database. On Windows, copy data\leaderboard.sqlite3 to a safe location; on Linux service installs, copy /opt/leaderboard-bot/data/leaderboard.sqlite3. Keep your .env separately and privately. Restart after copying. Restore only while stopped.

For Docker, stop the bot and archive the volume from inside the existing container:

```sh
docker compose stop
# Temporarily start a shell container using the same volume to export a backup.
docker compose run --rm --no-deps --entrypoint tar bot -czf - -C /app/data . > leaderboard-data-backup.tar.gz
docker compose up -d
```

Use a POSIX shell for the Docker archive redirection; older Windows PowerShell versions can alter binary output. To restore in a POSIX shell, stop the bot, then run `docker compose run --rm --no-deps -T --entrypoint tar bot -xzf - -C /app/data < leaderboard-data-backup.tar.gz`, then start it again. Test backups before relying on them.

## Troubleshooting

| Problem | What to check |
|---|---|
| Bot never starts | Open logs/terminal. Confirm dependencies, .env filename, token and numeric IDs. |
| LoginFailure | Reset/copy the token privately; update .env and restart. |
| PrivilegedIntentsRequired | Enable Message Content Intent in the portal; check whether approval is required. |
| Images ignored | Correct channel/server IDs, bot online, Message Content Intent and channel permissions. |
| TesseractNotFoundError | Install OCR engine; Windows TESSERACT_CMD must point to the actual executable. |
| ❌ on readable image | Try a direct screenshot, larger stats text, less compression; unsupported suffixes need maintainer verification. |
| No reactions | Add Reactions and Read Message History permissions, plus channel overrides. |
| ✅ but board delayed | Score was saved; display retries every two minutes. Check leaderboard channel permissions/logs. |
| Scores vanish after redeploy | Database path is on temporary storage; restore a backup and configure persistent storage. |

An image may still pass OCR with an incorrect value. Validate more examples before running prizes or treating this as an authoritative record. An abbreviated screenshot cannot establish the game's full hidden number or prove who owns the account.
