# Screenshot Leaderboard Bot

A Discord bot that reads Fortnite Stats screenshots using local Tesseract OCR and maintains five all-time Top 10 leaderboards: Packs Opened, Money Earned, Grade Coins, Shiny Cards and Total Playtime.

Start with [INSTALL.md](INSTALL.md) for Discord setup, Windows/Linux/Proxmox/Docker installation, configuration, updates, backups and troubleshooting. Copy [SCREENSHOT_GUIDE.md](SCREENSHOT_GUIDE.md) into Discord and pin it for players. [ROADMAP.md](ROADMAP.md) holds future improvements; [TEST_RESULTS.md](TEST_RESULTS.md) records validation and limitations.

## Player workflow

Upload one or two PNG, JPG, JPEG or WebP screenshots (up to 15 MB each) in the configured submissions channel. The new blue Player Stats layout supplies the username below its title and the visible statistics. The submitting Discord user ID is the permanent record key; the Epic name is a mutable display field. Each numeric category keeps its highest recorded value. The old green Stats layout still supports its original three numeric categories. It does not add screenshot totals together. An older screenshot can succeed without changing any stored score.

| Reaction | Meaning |
|---|---|
| ⏳ | Queued or processing |
| ✅ | Visible supported stats were read and saved; missing off-screen fields stay unchanged |
| ❌ | Processing failed; scores were not updated by that attempt |

The bot edits five persistent leaderboard messages instead of posting new ones for every submission. Ties share a rank, with Discord user ID used to order tied entries. All players remain in the database even outside the Top 10. A successful database save remains valid if a Discord display update fails; the public boards retry every two minutes. Discord outages can prevent reactions from appearing.

## Player names, partial views and playtime

The blue header's username (for example `CROSSBAR_CHRIS`) is shown alongside the uploader's Discord mention. Changing an Epic or Discord display name does not create a second score record because scores remain keyed by Discord ID. A current-name profile and observed-name history are stored under that same ID. Different Discord accounts are never merged merely because their screenshots show the same name. Existing records migrate automatically; until a new accepted named screenshot arrives, they use their saved Discord display name.

A profile uses the newest accepted screenshot **message posting time**, so startup replay of older messages cannot revert a name. Screenshot capture time and actual Epic account ownership are not verified. Posting an old photo as a new message can therefore change the displayed name, but still does not duplicate the Discord record. Ask players to submit only their own screenshots.

Keep Money Earned, Grade Coins and at least one additional statistic visible in a new-layout screenshot, with the header/name intact. Missing off-screen packs/playtime are allowed and never overwrite stored scores. Visible but uncertain labels/values cause rejection. Unknown stats remain unrecorded, not fabricated as zero; unrecorded categories are excluded from their rankings. Playtime is stored as integer seconds and displayed as days/hours/minutes/seconds. All five numeric categories retain independent maxima.

Two modern scroll views can be attached to one message if both usernames agree exactly. Both images must pass; a mismatch or unreadable view rejects the whole submission without a partial save. Overlapping stats use the maximum, not a sum. Two legacy views cannot be combined because they do not expose a verified common header name. Separate one-image messages remain supported. Already-successful historical messages are not re-read just to fill new fields; send a fresh screenshot when needed.

The first three public message IDs are preserved; the two new category messages are created automatically. `/rank`, `/leaderboard` and `/admin-set` include the new categories. Admin removal clears all recorded numeric scores while retaining name/audit history.

## Commands

| Command | Purpose |
|---|---|
| `/rank` | Private standings across all five categories |
| `/leaderboard` | Private rankings by category and page, including players outside the Top 10 |
| `/admin-set` | Replace one existing player's score in a selected category, including lowering an OCR mistake; requires a reason |
| `/admin-remove` | Remove an existing player from all rankings; requires a reason and `confirm:True` |

Money corrections accept a full integer or an abbreviation such as `$26.7Qa` or `1.93Qi`. Packs, coins and shiny cards accept whole counts without suffixes. Playtime accepts whole seconds or `03d 09h 41m 30s` (hours <24, minutes/seconds <60). Admin values must resolve to nonnegative whole units below 10^60. Setting `confirm:False` cancels removal. There is no built-in undo command.

With `ADMIN_ROLE_ID` configured, the exact role is required even for administrators and the server owner. Without it, admin commands require Manage Server permission. Discord command visibility must also be configured for the role; see [installation instructions](INSTALL.md#moderator-role-and-command-access).

A correction changes only the selected category. Removal is not a ban: later submissions, queued images or newly accepted historical failures can raise a corrected score or re-add a removed player. Previously successful message IDs stay skipped during recovery. Each admin edit is saved atomically with its audit record and delivery queue entry; an audit-write failure rolls back the edit.

## Recovering failed images

On every full process startup, the bot scans the configured submissions text channel for supported one- or two-image messages posted during the previous 72 hours. It retries failed/unprocessed messages, including offline uploads and interrupted work, and skips already-successful message IDs. Recovered messages receive ✅ and lose the bot's own ❌/⏳ reactions. Historical failures do not generate repeated public reply messages.

`HISTORY_LOOKBACK_HOURS` changes the window (default 72; 0 disables; maximum 720). The cutoff uses original posting time. Restart after installing an OCR fix before the image ages out of that window. The scan is not periodic and does not rerun on ordinary gateway reconnects. It needs View Channel and Read Message History. It excludes threads, other channels, bot posts, links/embeds, more than two attachments and unsupported formats. Deleted or inaccessible originals cannot be recovered; successful message edits are not reprocessed.

One OCR worker uses a 50-item queue. Backfill waits for queue space; a large backlog may delay live submissions. A full live queue produces feedback and leaves that message eligible for the next startup scan. History-fetch failures due to Discord/permissions retry after 60 seconds. A scan-complete log means eligible images have been queued, not that OCR has finished. Recovery depends on Discord retaining the original; this is not a local image archive or a persistent job queue beyond the history window.

## Audit channel and data

Set `AUDIT_CHANNEL_ID` to an existing private text channel. The bot never creates channels/roles or changes their permissions. The channel receives:

- Admin corrections/removals: moderator/player IDs, timestamp, action, reason and exact old/new values.
- Screenshot failures: uploader ID, failure time, safe reason and a link to the original image message. The image is not copied or reuploaded. Raw tracebacks remain in service logs.

Normal successful submissions do not post audit-channel messages. The same failed message/reason is reported once; a different reason creates a new report. Delivery queues survive restarts and retry every 60 seconds, with immediate delivery attempted after worker failures. Each flush handles up to 20 admin entries and 20 failure reports. Mention notifications are disabled. If a pending failure report is delivered after recovery, it is labeled recovered; already delivered reports remain historical records.

If Discord accepts a report just before a crash/network ambiguity prevents saving its delivery marker, a duplicate can occur; its audit/failure ID identifies it. Deleted delivered reports are not recreated. Disabling channel delivery retains local audit records and queues; enabling it later sends pending reports. Changing channels affects pending reports, not previously delivered messages. Old pre-feature admin audits are not automatically broadcast; older screenshot failures are reported if retried and still failing. A failed database write may make durable debugging impossible; check service logs.

SQLite stores scores, leaderboard message IDs, submission audits, admin edits and delivery markers. Images stay in memory during processing and are not archived. Keep one bot instance per server/database and use persistent storage. Back up the database and keep `.env` private. Audit data is an operational record, not tamper-proof storage.

## How OCR works

For the new blue Player Stats layout, OpenCV finds a candidate header, confirms its title, reads the username below it and locates the row/value-box geometry. Label aliases require two agreeing classifications (fuzzy similarity >=0.84 and separation from the next class); numeric values and usernames require two agreeing readings with word confidence >=65 and no accepted conflicting readings. Time-specific O/0 normalization is restricted to a structured day/hour/minute/second string. The reader has no fixed screenshot x/y coordinates. The layout, colors and crop proportions remain heuristics.

For the legacy layout, Pillow prepares four full-image versions for Tesseract. The reader uses fuzzy stat-label matching and reads the numeric value after the colon on the same detected line. It requires at least two matching accepted values per statistic, numeric token confidence >=65, and no conflicting supported values. If full-image reading fails, OpenCV finds up to two wide green-header candidates, derives panel crops from their geometry and tries three bright-neutral-text masks with block OCR. No screenshot x/y coordinates are fixed. OpenCV is installed through `requirements.txt` and brings NumPy; no paid API is used.

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

On Debian use `.venv/bin/python` instead of `python`; Windows uses `.venv\Scripts\python.exe`. No token is needed for these offline checks. The current suite discovers 71 tests: 66 pass and five private-image cases skip without `OCR_SAMPLE_DIR` and `PLAYER_STATS_SAMPLE_DIR`. The new two samples were also tested locally with both variables enabled: 70 passed and one corrupt cached old fixture skipped. See [TEST_RESULTS.md](TEST_RESULTS.md) for sample outcomes and platform/live-test limits. User testing confirmed bot startup, a sample submission, admin audit delivery and the previously rejected photo passing; this is not validation across every hosting platform or Discord edge case.

## Sources

- [Discord Developer Portal](https://discord.com/developers/applications)
- [discord.py intents](https://discordpy.readthedocs.io/en/stable/intents.html)
- [discord.py commands](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [discord.py message history](https://discordpy.readthedocs.io/en/stable/api.html#discord.TextChannel.history)
- [Discord command permissions](https://support-apps.discord.com/hc/en-us/articles/26501869403159-Command-Permissions)
- [Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
