# 72-hour startup recovery and screenshot failure reports

Built from repository commit 651d845, including the preceding OCR panel fix. This update adds startup history recovery and failure reporting to your existing audit channel. It never creates channels or changes role permissions.

## Behavior

Every full process startup scans #leaderboard-submissions (the configured channel ID), oldest first, for messages posted within the previous 72 hours. It retries failed messages and previously unprocessed supported image attachments, including images uploaded while the bot was offline or left unfinished by a restart. Previously successful message IDs are skipped: we do not OCR them again, sum totals, or undo admin corrections by replaying successful old screenshots.

Only non-bot messages in your configured server/channel with exactly one PNG, JPG, JPEG or WebP attachment are queued from history. The normal size limit and OCR validation still apply. Multiple attachments and unsupported files are not retried from history; new invalid uploads keep their feedback. Message timestamp, not failure time or edit time, defines the retry window. Successful messages stay skipped even if someone edits them. Posted links/embeds, threads, other channels and deleted messages are not backfilled.

The scan runs **once per process startup**, not every minute and not again on ordinary gateway reconnects. Updating code and restarting the systemd service triggers it. It uses fresh Discord message/attachment data. If history fetch fails due to Discord or missing permissions, it retries after 60 seconds. Already queued history IDs are deduplicated during that process. A new process can retry a still-failing image again.

Recovered images receive ✅; the bot removes its own ❌ and ⏳ reactions. Still-unreadable images retain ❌. Historical retries do not post another failure reply in submissions. New failures retain the existing player-facing reply. The single OCR worker and 50-item queue are shared with live uploads; a history scan waits for space instead of dropping backlog jobs. Large backlogs can delay new processing; a full live queue gives feedback and remains eligible for the next startup scan. Scan-complete logs mean candidates have been queued, not that OCR has finished.

You get a rolling 3-day opportunity to fix OCR **if you install/restart the fix before the original upload ages out of the 72-hour startup window**. Recovery relies on Discord retaining the message and the bot having access. It is not an image archive or a durable local job queue beyond that window. Failed historical screenshots newly accepted by a fixed reader can raise scores or re-add a removed player; admin removal is still not a ban.

## Configuration

No new setting is required: 72 hours is the default. Optionally add to your LOCAL .env:

```dotenv
HISTORY_LOOKBACK_HOURS=72
```

Set 0 to disable. Values 0–720 hours are accepted; invalid settings fail startup. Preserve your current token, IDs, role and database path. Restart after changes. Never upload your local .env to GitHub.

In submissions, the bot needs **View Channel** and **Read Message History**, in addition to its existing reaction/reply permissions. It uses Discord's paginated history, not just the newest 100 messages. Source: https://discordpy.readthedocs.io/en/stable/api.html#discord.TextChannel.history

## Debugging in your existing audit channel

Your current AUDIT_CHANNEL_ID also receives failure reports for OCR, image validation, attachment access/download, queue capacity and safe processing-error categories. Reports contain a link to the **original image message**, uploader ID, failure time and reason (such as `Could not confidently read Total Money Earned`). The image is not copied/reuploaded and the channel is not created. Opening the link requires access to the original message. If it is deleted, its link cannot recover the image.

The same message and same reason are recorded once for channel delivery. Repeating the same failure after every restart does not normally produce more reports. A different reason for that message produces a new report. Failure logs are queued in SQLite and retried with the normal 60-second audit delivery task; immediate delivery is also attempted after worker failures. Safe descriptions go to Discord, while raw exception tracebacks stay in service logs. If the database itself cannot be written, a durable failure report may be impossible; inspect journalctl in that case.

An old queued report delivered after its message succeeds is labeled as recovered. An already delivered failure embed remains a historical record and is not edited to track later successes. Mentions do not ping users. A crash/network ambiguity between Discord accepting a report and its local delivery marker can still cause a duplicate; the failure ID identifies it. Delivered reports are not recreated if manually deleted from Discord.

Use a private audit text channel and grant the bot View Channel, Send Messages and Embed Links there. Setting AUDIT_CHANNEL_ID to 0 disables channel delivery; database records remain. Pending failure reports can be delivered when it is enabled later. Old failures from before this update are reported if retried and still failing, not blindly reposted from old audit rows.

## Update container 205

Upload the ZIP contents to matching leaderboard_bot/ paths on GitHub, including the new submission_replay.py and tests/test_submission_replay.py. Do not nest another leaderboard_bot directory. Then run inside container 205:

```sh
systemctl stop leaderboard-bot
mkdir -p /root/leaderboard-backups
cp /opt/Discord_Bots/leaderboard_bot/data/leaderboard.sqlite3 /root/leaderboard-backups/leaderboard-$(date +%Y%m%d-%H%M%S).sqlite3
cd /opt/Discord_Bots
git pull --ff-only
cd leaderboard_bot
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

Expect **52 tests, OK (skipped=3)** without private screenshot fixtures: 49 tests pass and three optional private-image regression tests skip. Stop and inspect any failure before proceeding. There are no new dependencies beyond the previous OCR fix; pip ensures that fix's requirements are installed too.

Optionally add HISTORY_LOOKBACK_HOURS=72 to .env, although leaving it out uses that default. Leave AUDIT_CHANNEL_ID pointing to your current audit channel. Then:

```sh
chown -R leaderboard:leaderboard /opt/Discord_Bots/leaderboard_bot
chmod 600 .env
systemctl start leaderboard-bot
systemctl status leaderboard-bot --no-pager
journalctl -u leaderboard-bot -n 80 --no-pager -l
```

Look for `Scanning submission history` and `History scan finished`. Wait for the OCR worker to process queued items. An image from the previous 72 hours that failed before the OCR fix should now update its original reactions if it becomes readable. No repost is required for that case. Normal screenshots still keep highest lifetime values and audit logs keep original uploader IDs.

## Validation and rollback

Local tests cover the prior features plus the 72-hour cutoff, inclusion of failed/offline messages, success skipping, channel/author/file filters, live/history duplicate prevention, queue backpressure, disabled/invalid settings, original-uploader processing, successful retry reactions, quiet historical failures, failure embeds/links/reasons, durable audit retry, same-reason deduplication across reopen, safe error descriptions, and transactional failure recording. Real Discord history access/rate limits, server permissions, large backlogs and production startup still need verification on your server. Docker includes the new module but was not built.

New submission_failures records are added without deleting existing scores, audits, role settings or board IDs. If rolling code back, stop the bot and return to the previous Git revision; the source before this update is 651d845. Old code ignores the new table. Score changes from newly recovered screenshots remain unless you explicitly restore a database backup or use admin corrections. Back up current data before any database replacement.
