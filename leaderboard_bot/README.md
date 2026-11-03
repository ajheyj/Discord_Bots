# Screenshot Leaderboard Bot

A Discord bot that reads Fortnite Stats screenshots using local Tesseract OCR and maintains three all-time Top 10 leaderboards: Packs Opened, Total Money Earned and Total Grade Coins Earned.

Start with [INSTALL.md](INSTALL.md) for Discord setup, Windows/Linux/Proxmox/Docker installation, configuration, updates, backups and troubleshooting. Copy [SCREENSHOT_GUIDE.md](SCREENSHOT_GUIDE.md) into Discord and pin it for players. [ROADMAP.md](ROADMAP.md) holds future improvements; [TEST_RESULTS.md](TEST_RESULTS.md) records validation and limitations.

## Player workflow

Upload one PNG, JPG, JPEG or WebP image, up to 15 MB, in the configured submissions channel. The bot identifies the Discord uploader as the player, extracts all three stats, and saves each category's highest recorded value. It does not add screenshot totals together. An older screenshot can succeed without changing any stored score.

| Reaction | Meaning |
|---|---|
| ⏳ | Queued or processing |
| ✅ | All three stats were read and saved |
| ❌ | Processing failed; scores were not updated by that attempt |

The bot edits three existing leaderboard messages instead of posting new ones for every submission. Ties share a rank, with Discord user ID used to order tied entries. All players remain in the database even outside the Top 10. A successful database save remains valid if a Discord display update fails; the public boards retry every two minutes. Discord outages can prevent reactions from appearing.

## Commands

| Command | Purpose |
|---|---|
| `/rank` | Private standings across all three categories |
| `/leaderboard` | Private rankings by category and page, including players outside the Top 10 |
| `/admin-set` | Replace one existing player's score in a selected category, including lowering an OCR mistake; requires a reason |
| `/admin-remove` | Remove an existing player from all rankings; requires a reason and `confirm:True` |

Money corrections accept a full integer or an abbreviation such as `$26.7Qa` or `1.93Qi`. Packs and coins accept whole counts without suffixes. Admin values must resolve to nonnegative whole units below 10^60. Setting `confirm:False` cancels removal. There is no built-in undo command.

With `ADMIN_ROLE_ID` configured, the exact role is required even for administrators and the server owner. Without it, admin commands require Manage Server permission. Discord command visibility must also be configured for the role; see [installation instructions](INSTALL.md#moderator-role-and-command-access).

A correction changes only the selected category. Removal is not a ban: later submissions, queued images or newly accepted historical failures can raise a corrected score or re-add a removed player. Previously successful message IDs stay skipped during recovery. Each admin edit is saved atomically with its audit record and delivery queue entry; an audit-write failure rolls back the edit.

## Recovering failed images

On every full process startup, the bot scans the configured submissions text channel for supported single-image messages posted during the previous 72 hours. It retries failed/unprocessed messages, including offline uploads and interrupted work, and skips already-successful message IDs. Recovered messages receive ✅ and lose the bot's own ❌/⏳ reactions. Historical failures do not generate repeated public reply messages.

`HISTORY_LOOKBACK_HOURS` changes the window (default 72; 0 disables; maximum 720). The cutoff uses original posting time. Restart after installing an OCR fix before the image ages out of that window. The scan is not periodic and does not rerun on ordinary gateway reconnects. It needs View Channel and Read Message History. It excludes threads, other channels, bot posts, links/embeds, multiple attachments and unsupported formats. Deleted or inaccessible originals cannot be recovered; successful message edits are not reprocessed.

One OCR worker uses a 50-item queue. Backfill waits for queue space; a large backlog may delay live submissions. A full live queue produces feedback and leaves that message eligible for the next startup scan. History-fetch failures due to Discord/permissions retry after 60 seconds. A scan-complete log means eligible images have been queued, not that OCR has finished. Recovery depends on Discord retaining the original; this is not a local image archive or a persistent job queue beyond the history window.

## Audit channel and data

Set `AUDIT_CHANNEL_ID` to an existing private text channel. The bot never creates channels/roles or changes their permissions. The channel receives:

- Admin corrections/removals: moderator/player IDs, timestamp, action, reason and exact old/new values.
- Screenshot failures: uploader ID, failure time, safe reason and a link to the original image message. The image is not copied or reuploaded. Raw tracebacks remain in service logs.

Normal successful submissions do not post audit-channel messages. The same failed message/reason is reported once; a different reason creates a new report. Delivery queues survive restarts and retry every 60 seconds, with immediate delivery attempted after worker failures. Each flush handles up to 20 admin entries and 20 failure reports. Mention notifications are disabled. If a pending failure report is delivered after recovery, it is labeled recovered; already delivered reports remain historical records.

If Discord accepts a report just before a crash/network ambiguity prevents saving its delivery marker, a duplicate can occur; its audit/failure ID identifies it. Deleted delivered reports are not recreated. Disabling channel delivery retains local audit records and queues; enabling it later sends pending reports. Changing channels affects pending reports, not previously delivered messages. Old pre-feature admin audits are not automatically broadcast; older screenshot failures are reported if retried and still failing. A failed database write may make durable debugging impossible; check service logs.

SQLite stores scores, leaderboard message IDs, submission audits, admin edits and delivery markers. Images stay in memory during processing and are not archived. Keep one bot instance per server/database and use persistent storage. Back up the database and keep `.env` private. Audit data is an operational record, not tamper-proof storage.

## How OCR works

Pillow prepares four full-image versions for Tesseract. The reader uses fuzzy stat-label matching and reads the numeric value after the colon on the same detected line. It requires at least two matching accepted values per statistic, numeric token confidence >=65, and no conflicting supported values. If full-image reading fails, OpenCV finds up to two wide green-header candidates, derives panel crops from their geometry and tries three bright-neutral-text masks with block OCR. No screenshot x/y coordinates are fixed. OpenCV is installed through `requirements.txt` and brings NumPy; no paid API is used.

The photographed-panel fallback resolved a clear image whose full-scene text segmentation failed; extra rows such as Shiny Cards are ignored. Header colors, light-text assumptions and crop proportions are game-specific heuristics. Changed labels, suffixes, colors, fonts or layouts can need edits to `ocr.py`. Fallback processing can take longer. Agreement reduces errors but Tesseract can repeat the same mistake. The reader cannot prove image authenticity or Fortnite account ownership. An unsupported token is discarded, so two supported readings can still agree despite another unknown-suffix reading; see the roadmap.

| Suffix | Multiplier |
|---|---|
| K | 10³ |
| M | 10⁶ |
| B | 10⁹ |
| T | 10¹² |
| Qa | 10¹⁵ |
| Qi | 10¹⁸ |

These game mappings were inferred, not verified with its developer. Suffixes are case-sensitive; verify new ones before extending `SUFFIXES` in `ocr.py`. Exact integer storage/ranking avoids floating-point loss. Money display rounds to three decimals, while stored values retain the screenshot's displayed precision; hidden precision cannot be recovered.

## Development and validation

From the bot folder with dependencies installed:

```sh
python -m unittest discover -s tests -v
python ocr.py "/path/to/image.png"
```

On Debian use `.venv/bin/python` instead of `python`; Windows uses `.venv\Scripts\python.exe`. No token is needed for these offline checks. The current suite discovers 52 tests: 49 pass and three optional private-image cases skip without `OCR_SAMPLE_DIR`. See [TEST_RESULTS.md](TEST_RESULTS.md) for sample outcomes and platform/live-test limits. User testing confirmed bot startup, a sample submission, admin audit delivery and the previously rejected photo passing; this is not validation across every hosting platform or Discord edge case.

## Sources

- [Discord Developer Portal](https://discord.com/developers/applications)
- [discord.py intents](https://discordpy.readthedocs.io/en/stable/intents.html)
- [discord.py commands](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [discord.py message history](https://discordpy.readthedocs.io/en/stable/api.html#discord.TextChannel.history)
- [Discord command permissions](https://support-apps.discord.com/hc/en-us/articles/26501869403159-Command-Permissions)
- [Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
