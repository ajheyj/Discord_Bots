# Operator guide: publishing and maintaining the shared policies

These documents describe the current leaderboard implementation. They are not a certification of legal compliance, and a policy does not implement deletion, retention controls or incident response by itself. Verify your actual hosting and practices before publishing. Independent hosts need their own operator identity/contact and accurate notices.

## Publish at the repository root

Upload README.md, TERMS.md, PRIVACY.md, SUPPORT.md, SECURITY.md, OPERATOR_GUIDE.md and CONTRIBUTING.md to the **top level** of Discord_Bots, alongside leaderboard_bot/. Do not replace leaderboard_bot/README.md with the repository README. No bot code, token or database change is part of this documentation update.

Once uploaded to a publicly readable main branch, the intended links are:

- Terms: https://github.com/ajheyj/Discord_Bots/blob/main/TERMS.md
- Privacy: https://github.com/ajheyj/Discord_Bots/blob/main/PRIVACY.md
- Support: https://github.com/ajheyj/Discord_Bots/blob/main/SUPPORT.md

Open each link while signed out to confirm accessibility. In the Discord Developer Portal, select the existing application and add the Terms and Privacy links to the corresponding application information fields. Keep them up to date. Expose the links through the application description/about information and the server's pinned bot instructions; an in-app policy command can be added separately. Publish a working **direct private operator contact** there as well. No operator email/Discord handle has been invented in these documents.

Discord requires an accurate public privacy notice and an accessible modification/deletion request route. Its App Discovery requirements also call for public Terms and Privacy links. Read the current official requirements rather than assuming this package alone satisfies every obligation:

- [Discord Developer Terms of Service, especially Section 5](https://support-dev.discord.com/hc/en-us/articles/8562894815383-Discord-Developer-Terms-of-Service)
- [Discord Developer Policy](https://support-dev.discord.com/hc/en-us/articles/8563934450327-Discord-Developer-Policy)
- [App Discovery content requirements](https://support-dev.discord.com/hc/en-us/articles/9489299950487-App-Discovery-Content-Requirements-Policy)

## Check the deployed behavior

- Confirm the version includes private /submit sessions, partial OCR, result snapshots and audit screenshot copies before describing those features as active. Old versions may use public uploads/replies/reactions instead.
- Keep audit-channel access limited to intended moderators. Ordinary members must not gain screenshot access through inherited permissions. The bot does not configure channel privacy for you.
- Grant Attach Files only where needed. Know the server's upload limit; oversized or evicted screenshots cannot be included in audit copies.
- Check the actual DATABASE_PATH, SPOOL_PATH, BACKUP_PATH, retention settings, host log retention and extra/off-host backups without exposing tokens.
- A 72-hour cache/history setting does not expire Discord audit posts or purge database history. Current code does not automatically prune scores, aliases, completed job records, session rows or Discord result messages.
- Retain user data only while necessary for stated bot functions. Review old records and implement/manual-operate appropriate cleanup. Do not claim a scheduled purge that is not running.
- No source-code license has been selected in this package. Decide one separately before describing the repository as open source or granting reuse rights.

## Handle a privacy request end to end

1. Receive it privately and verify the requester through the relevant Discord account with minimal extra information. Identify the hosting operator; repository maintainers cannot delete independently hosted data they do not control.
2. Pause the affected processing. For the current single-instance leaderboard, stopping the service is the simplest way to avoid concurrent downloads, OCR, notification and history replay during deletion. Use the bot-specific installation guide.
3. Find the relevant Discord account/message IDs in **scores, player_profiles, player_names, audit, submission_results, submission_failures, queue_jobs, dm_sessions and admin_audit**. Include actor and target references and personally identifying reasons/snapshots, not just the score row. Related delivery markers and job/image directories need consistent handling too.
4. For access/correction, provide only the verified user's data, redact other people's information and apply relevant changes across records and bot-controlled displays. Do not send an entire server database to one user.
5. For deletion, remove or appropriately anonymize affected records and associated cached files, pending work, and bot-authored audit attachments/results/DM messages under your control as required. Handle public board entries and avoid retaining personal identifiers in free-text reasons. /admin-remove alone is insufficient and itself creates another audit entry.
6. Address original submissions and history recovery. Old server posts or DM images can recreate erased data on startup. Arrange removal of relevant originals under your/user/server control, or prevent their reimport before restarting. Turning HISTORY_LOOKBACK_HOURS off only temporarily does not solve later reimport. There is no per-user exclusion/deletion workflow in current code; do not invent one in notices or promise automatic erasure. If needed, keep affected processing disabled until the workflow is resolved.
7. Locate automatic, manual and off-host backups. Remove or rebuild affected copies as required rather than assuming seven-copy rotation always satisfies a deletion request. Record only the minimum restricted information needed to ensure a restored backup does not reintroduce deleted data. Reapply deletions before restoring a service to operation.
8. Confirm the request outcome privately, including any lawful retention limit or copy beyond your control. Check that queues, public boards and audit delivery do not recreate the data. Keep only a necessary, minimized request-handling record with appropriate access and retention.

Do not copy a live SQLite file as a backup without handling WAL data; use the documented consistent backup procedure. Avoid ad-hoc deletion SQL on the live service: relationships, audit snapshots, original Discord messages and backups all matter. A transactional administrative privacy tool would reduce manual mistakes, but is not included in this documentation package.

## Add another bot

Before launch, identify what it reads/writes, its permissions, data sources, public/private outputs, providers, retention, backup and deletion behavior. Add its own overview/install/configuration/tests and a bot-specific privacy section or linked supplement. Update the root bot list and service scope. Add new collection or disclosure only after the appropriate notice and user authorization. Do not apply leaderboard-specific claims such as local OCR to an unrelated bot.

New paid features, prizes, wagering, external AI services or other materially different processing need separate review before launch. A general policy is not blanket approval for future features.
