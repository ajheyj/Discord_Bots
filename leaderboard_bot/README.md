# Screenshot Leaderboard Bot

A Discord bot that reads Fortnite Stats screenshots using local Tesseract OCR and maintains five all-time Top 10 leaderboards: Packs Opened, Money Earned, Grade Coins, Shiny Cards and Total Playtime.

Start with [INSTALL.md](INSTALL.md) for Discord setup, Windows/Linux/Proxmox/Docker installation, configuration, updates, backups and troubleshooting. Copy [SCREENSHOT_GUIDE.md](SCREENSHOT_GUIDE.md) into Discord and pin it for players. [ROADMAP.md](ROADMAP.md) holds future improvements; [TEST_RESULTS.md](TEST_RESULTS.md) records validation and limitations.

## Player workflow

Run **/submit** in the server. Its reply is visible only to you, and the bot DMs upload instructions. Send one or two PNG, JPG, JPEG or WebP screenshots per DM message, up to 15 MB each. The session lasts 24 hours; run /submit again to reopen it. Allow DMs from the server first. The bot privately acknowledges accepted jobs and DMs a before/after summary when finished. **/submission-result** privately retrieves your latest completed result if DMs become blocked.

No new public processing replies or reactions are posted. Existing submissions-channel uploads remain supported for compatibility and startup recovery, but receive private DM responses. To keep that channel clean, direct players to /submit and optionally make it read-only except for application commands. The bot does not edit channel permissions or delete anyone's posts. The public leaderboards still show saved scores and player names. Screenshots and result summaries may be copied to the configured moderator audit channel; disclose this to players and restrict that channel appropriately.

The submitting Discord user ID is the permanent record key; the Epic name is a mutable display field. Each numeric category keeps its highest recorded value. An older screenshot can succeed without changing any score. Totals are never added together.

The bot edits five persistent leaderboard messages instead of posting new ones for every submission. Ties share a rank, with Discord user ID used to order tied entries. All players remain in the database even outside the Top 10. A successful database save remains valid if a Discord display update fails; dirty public boards refresh in batches every 30 seconds by default. Discord outages can delay DMs, audit reports or board edits.

## Player names, partial views and playtime

The blue header's username (for example `CROSSBAR_CHRIS`) is shown alongside the uploader's Discord mention. Changing an Epic or Discord display name does not create a second score record because scores remain keyed by Discord ID. A current-name profile and observed-name history are stored under that same ID. Different Discord accounts are never merged merely because their screenshots show the same name. Existing records migrate automatically; until a new accepted named screenshot arrives, they use their saved Discord display name.

A profile uses the newest accepted screenshot **message posting time**, so startup replay of older messages cannot revert a name. Screenshot capture time and actual Epic account ownership are not verified. Posting an old photo as a new message can therefore change the displayed name, but still does not duplicate the Discord record. Ask players to submit only their own screenshots.

Each stat is evaluated independently. At least one confidently read numeric value is enough to save a submission. Unreadable, conflicting or off-screen values are omitted and leave existing scores unchanged. Unknown stats stay unrecorded, never fabricated as zero. Playtime is optional and stored in seconds. An unreadable username does not prevent numeric updates to the known Discord account; its previous display name remains.

Two views merge per-category maxima. If both readable usernames are present, they must agree exactly; a mismatch rejects the submission. A wholly unreadable image can be skipped while values from the other image are saved. Recognition notes appear in the private summary and audit report. Individual fields still require two agreeing accepted readings; partial recognition does not lower confidence thresholds. Already-successful messages are not re-read merely to fill missing fields; send a fresh screenshot if needed.

The first three public message IDs are preserved; the two new category messages are created automatically. `/rank`, `/leaderboard` and `/admin-set` include the new categories. Admin removal clears all recorded numeric scores while retaining name/audit history.

## Commands

| Command | Purpose |
|---|---|
| `/submit` | Open a private, 24-hour screenshot-upload session in DMs |
| `/submission-result` | Privately view your own latest completed submission summary |
| `/rank` | Private standings across all five categories |
| `/leaderboard` | Private rankings by category and page, including players outside the Top 10 |
| `/admin-set` | Replace one existing player's score in a selected category, including lowering an OCR mistake; requires a reason |
| `/admin-remove` | Remove an existing player from all rankings; requires a reason and `confirm:True` |
| `/queue` | Private moderator view of durable job counts, oldest pending age, reserved image storage, worker and backup status |

Money corrections accept a full integer or an abbreviation such as `$26.7Qa` or `1.93Qi`. Packs, coins and shiny cards accept whole counts without suffixes. Playtime accepts whole seconds or `03d 09h 41m 30s` (hours <24, minutes/seconds <60). Admin values must resolve to nonnegative whole units below 10^60. Setting `confirm:False` cancels removal. There is no built-in undo command.

With `ADMIN_ROLE_ID` configured, the exact role is required even for administrators and the server owner. Without it, admin commands require Manage Server permission. Discord command visibility must also be configured for the role; see [installation instructions](INSTALL.md#moderator-role-and-command-access).

A correction changes only the selected category. Removal is not a ban: later submissions, queued images or newly accepted historical failures can raise a corrected score or re-add a removed player. Previously successful message IDs stay skipped during recovery. Each admin edit is saved atomically with its audit record and delivery queue entry; an audit-write failure rolls back the edit.

## Recovering failed images

On every full process startup, the bot scans the configured submissions text channel for supported one- or two-image messages posted during the previous 72 hours. It retries failed/unprocessed messages, including offline uploads and interrupted work, and skips already-successful message IDs. It also scans DM histories for users who opened an upload session within the applicable window, considering messages posted before that session expired. Recovery sends no public reactions/replies. Existing reactions from older bot versions are not removed.

`HISTORY_LOOKBACK_HOURS` changes the window (default 72; 0 disables; maximum 720). The cutoff uses original posting time. Restart after installing an OCR fix before the image ages out of that window. The scan is not periodic and does not rerun on ordinary gateway reconnects. It needs View Channel and Read Message History. It excludes threads, other channels, bot posts, links/embeds, more than two attachments and unsupported formats. Deleted or inaccessible originals cannot be recovered; successful message edits are not reprocessed.

Accepted submissions now have a database-backed queue independent of the 72-hour history window. Pending jobs resume after restart even when older than that window. The history scan finds messages not already accepted and may retry terminal failures inside the window; it does not duplicate active or completed jobs. Admission limits also apply to history scans: skipped capacity/storage/per-user rejections are logged and can be retried on a later startup or new upload. There is no promise to accept unlimited messages. A scan-complete log means eligible messages were considered, not that OCR has finished. History API/permission failures retry after 60 seconds.

## Durable queue and resource limits

Admission validates attachment count/type/size, reserves image storage, and commits message/uploader IDs, posting time and attachment IDs to SQLite **before** a private acknowledgment. Images then download through two workers and are written atomically to private temporary spool files. Original attachment IDs are refreshed from Discord; a removed/changed attachment before caching fails rather than silently substituting a different image. After complete caching, OCR can continue even if the original message disappears. Before caching finishes, recovery still requires Discord access.

A single OCR worker launches an isolated subprocess for one submission at a time; its two screenshots are read sequentially. Queued OCR enforces `OMP_THREAD_LIMIT=1`, OpenCV `setNumThreads(1)`, and one BLAS thread before native imports. This controls parallelism, not an exact host/container CPU percentage. A one-core job can still look like ~50% on a two-vCPU container. Offline OCR commands are separate from the queued runner.

| Default | Value |
|---|---|
| Pending capacity | 2,000 submissions, subject to storage/space limits |
| Pending per Discord user | 5 submissions |
| Image spool budget | 2,048 MiB reserved across pending and retained terminal jobs |
| Minimum free disk margin | 512 MiB, accounting for downloads already promised |
| Download workers | 2 |
| Download stage deadline | 90 seconds per submission attempt |
| OCR deadline | 180 seconds per submission attempt |
| Retry budget | 3 attempts per stage for transient errors |
| Retry delay | 60 seconds, then exponential backoff |
| Failed image retention | Up to 72 hours; may be evicted sooner under storage pressure |
| Database backup | Every 24 hours, keeping 7 copies |
| Leaderboard refresh | Dirty batches every 30 seconds; periodic board health check every 5 minutes |

The queue does not hold all image bytes in RAM. At most two download stages and one OCR job run together. Local disk space and memory can still fail; actual throughput must exceed sustained arrivals for a backlog to drain. Large backlogs may take hours. Capacity/storage/per-user rejections are explicit and are **not accepted jobs**. 500 people with two 2 MiB screenshots need about 2,000 MiB; 500 people with maximum-size screenshots could need 15,000 MiB and exceed the default budget. Increase storage settings only when disk space permits.

Temporary downloads/timeouts retry with a deadline and finite budget. Unreadable/invalid screenshots fail without repeated OCR attempts; transient OCR process failures retry. A timed-out/cancelled OCR job terminates its process tree on the tested Linux path, preventing leftover Tesseract CPU workers. Failed jobs move out of the pending queue and keep an audit record. Interrupted claims are recovered, with attempts retained; repeated crashes cannot silently reset the attempt budget. A single-instance database lock prevents two local workers using the same queue. Supervision restarts stopped task loops and reclaims abandoned stale claims; hardware/filesystem/database failures still require operator intervention.

Scores, name changes, the successful message marker and job completion commit in one transaction. A crash before commit can cause re-OCR; a crash after commit does not double-save the score or overwrite an admin correction. Private result delivery retries independently of score saving. Permanently blocked DMs stop retrying; /submission-result remains available. Temporary Discord errors retry without changing scores. Successful cached images are kept until audit delivery or the retention limit; without an audit channel, successful files are deleted immediately. Failed images may also remain until the retention limit. Terminal caches can be evicted sooner under storage pressure. Dedicated spool directories are required because unreferenced numeric job folders are cleaned after database restoration.

Daily backups use SQLite's backup API, including committed WAL contents, with integrity checks and retention. They contain scores, queue metadata and audits, **not cached screenshots or .env**. Keep an off-host backup too. For full pending-image disaster recovery, back up the entire stopped data directory/volume in addition to credentials. `/queue` uses the same moderator role/Manage Server fallback as the other admin commands. See [INSTALL.md](INSTALL.md) for configuration, WAL-safe backup/update and restoration instructions.

## Audit channel and data

Set `AUDIT_CHANNEL_ID` to an existing private text channel. The bot never creates channels/roles or changes their permissions. The channel receives:

- Admin corrections/removals: moderator/player IDs, timestamp, action, reason and exact old/new values.
- Every completed screenshot result, including partial success and failure: Discord ID, recognized values, exact saved before/after snapshot, omitted fields, recognition notes and private delivery status when available.
- Cached screenshots copied as attachments when each fits the audit channel's upload limit. The original message link is included, but a DM link is visible only to its participants. If files were evicted/unavailable or too large, the report says so. Grant Attach Files permission in the audit channel.

Delivery queues survive restarts and retry every 60 seconds. A flush sends up to 20 admin entries and 20 submission summaries (plus any older failure records). Mention notifications are disabled. The bot never creates or secures channels. With audit delivery disabled, local snapshots remain; enabling it later sends pending reports, though their images may have expired.

A crash or ambiguous network response after Discord accepts a DM/audit message but before its delivery marker is saved can cause a duplicate. Saved scores remain idempotent. Deleted delivered messages are not recreated. Changing channels affects pending reports. A failed database write can prevent durable debugging; service logs remain important.

SQLite stores scores, leaderboard message IDs, submission audits, admin edits and delivery markers. Accepted images are temporarily cached on disk while pending, retained until successful audit delivery or the configured retention period (possibly less under storage pressure). This temporary cache is not a permanent image archive. Keep one bot instance per server/database and use persistent storage. Back up the database and keep `.env` private. Audit data is an operational record, not tamper-proof storage.

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

On Debian use `.venv/bin/python` instead of `python`; Windows uses `.venv\Scripts\python.exe`. No token is needed for these offline checks. The current suite discovers 100 tests: 95 pass and five private-image cases skip without `OCR_SAMPLE_DIR` and `PLAYER_STATS_SAMPLE_DIR`. A 500-job/two-files-each simulation reaches 471 successful and 29 deliberately failed outcomes after retries and a restart, with one OCR and at most two downloads. This uses synthetic small files and fake Discord/OCR, not a 1,000-photo CPU/throughput benchmark. Both real supplied new-layout screenshots also pass through the new single-thread subprocess with exact expected values. See [TEST_RESULTS.md](TEST_RESULTS.md) for sample outcomes and platform/live-test limits. User testing confirmed bot startup, a sample submission, admin audit delivery and the previously rejected photo passing; this is not validation across every hosting platform or Discord edge case.

## Sources

- [Discord Developer Portal](https://discord.com/developers/applications)
- [discord.py intents](https://discordpy.readthedocs.io/en/stable/intents.html)
- [discord.py commands](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [discord.py message history](https://discordpy.readthedocs.io/en/stable/api.html#discord.TextChannel.history)
- [Discord command permissions](https://support-apps.discord.com/hc/en-us/articles/26501869403159-Command-Permissions)
- [Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
