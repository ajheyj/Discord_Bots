# Privacy Policy

Last updated: November 14, 2026

## 1. Who this covers and how to contact us

This policy describes Discord bot instances operated by the maintainer of [ajheyj/Discord_Bots](https://github.com/ajheyj/Discord_Bots) and identified as maintainer-operated in their application/server information. The currently documented bot is Screenshot Leaderboard. Future bots must be described here or in a linked bot-specific notice before their data collection is enabled.

For help or a privacy request, contact the hosted bot's operator privately through the server owner or moderators. Ask them to route a **bot privacy request** to the operator. Include the bot name and your Discord account ID, and identify whether you want access, correction or deletion. See [SUPPORT.md](SUPPORT.md). Do not publish personal information in GitHub issues. Independently hosted copies are controlled by their respective hosts, who must provide their own identity, contact route and accurate privacy notice.

## 2. Information the leaderboard bot processes

| Information | Purpose and handling |
|---|---|
| Discord account ID and display name | Associate scores with a stable account; display player identity and route responses |
| Server, channel, role and message IDs; message links and posting times | Apply configured boundaries/permissions, locate submissions, recover queued work and maintain bot messages |
| Screenshot attachment IDs, filenames, sizes and image bytes | Validate, download, temporarily cache and read submitted screenshots; copy available images to the configured audit channel |
| Screenshot content, including Epic display names and visible game statistics | Extract supported values and maintain public lifetime leaderboards; incidental visible content is included in the image copy |
| Accepted stats, current/previous observed Epic names, score snapshots and result notes | Maintain rankings across name changes, explain updates and review incorrect results |
| Processing failures, queue state, retries, delivery status and operational logs | Diagnose errors, recover work, control resource use and prevent duplicate processing |
| Moderator actor/target IDs, correction/removal reasons and before/after values | Enforce command permissions and provide an administrative audit trail |
| DM session account ID and expiration timestamp | Authorize private screenshot uploads for 24 hours and recover eligible missed submissions |
| Support information you choose to provide | Answer questions, investigate a report and handle privacy requests |

The bot receives message events and command information made available to it by Discord and its configured permissions. Its submission handler selects supported images from the configured submissions channel and DM upload sessions; it is not a general archive of every server conversation. It does not intentionally store ordinary non-submission message bodies or record voice conversations. Do not assume Discord permissions or bot code prevent incidental content appearing in submitted images or diagnostic errors.

The current bot does not request an Epic login, verify Epic account ownership, collect payment details, or use advertising analytics. Do not provide passwords, bot tokens or other sensitive information in screenshots or support messages.

## 3. How information is used and who can see it

**Public rankings:** Server members with access to leaderboard channels may see Epic/display names, Discord mentions, scores and ranks. Private command results do not hide the public boards.

**Private interaction:** /submit privately acknowledges the command, then opens a DM upload session. The bot sends queue notices and result summaries in DMs. /submission-result, /rank and /leaderboard respond privately to the caller. These communications still pass through Discord and can be accessed by the bot operator as needed to operate or troubleshoot the service.

**Moderator audit copies:** A submission directs the bot to make the disclosed operational audit copy. When an audit channel is configured, its authorized viewers may see screenshot attachments, uploader identity, processing outcomes, recognition warnings and saved before/after values. The bot copies cached images when available and within the channel's upload limit. A DM message link alone cannot be opened by moderators who are not its participants. Audit screenshots can include incidental personal details; review images before submitting.

**Hosting and support:** Operators with authorized access to the host/database may inspect records for the stated functions, troubleshooting, security and privacy requests. For the maintainer's current deployment, OCR runs locally with Tesseract; screenshot content is not sent to an external OCR or generative-AI provider. Independently hosted copies may have different infrastructure and need their own notice. Discord processes messages and files under [its own Privacy Policy](https://discord.com/privacy). Public GitHub support activity is handled by GitHub under [its Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

The current service does not sell personal data, use it for targeted advertising or use submissions to train machine-learning models. Information is not shared for unrelated purposes. Any legally required disclosure or processing by a necessary hosting/service provider must comply with applicable law and Discord's developer requirements.

## 4. Storage and retention

Records are stored in a local SQLite database on the host running the bot. Images use a temporary local spool. Defaults can be changed by an operator; configuration changes must be reflected in the applicable notice.

| Data | Current default behavior |
|---|---|
| Accepted pending jobs and cached images | Retained while pending, including across restarts; not automatically deleted merely because a job becomes older than the history window |
| Successful cached images | Without an audit channel, deleted after processing. With audit delivery enabled, retained until audit delivery or the terminal-cache retention limit, normally up to 72 hours after completion; terminal caches may be evicted sooner for space |
| Failed cached images | Normally retained up to 72 hours after completion; may be evicted sooner for space; the limit is configurable |
| Scores, aliases, submission/audit snapshots, errors and queue metadata | No automatic age-based purge in the current code. Retained while necessary for the documented service and subject to manual review, correction and deletion requests |
| DM session records | Upload authorization expires after 24 hours. Expiration does not automatically delete the database row; it may support bounded startup history recovery |
| Bot DM messages, original server posts and audit-channel image/result copies | The bot has no automatic Discord-message expiration. Copies remain until deleted by a party with authority, subject to Discord's own handling |
| Automatic database backups | Normally one backup every 24 hours, keeping the seven most recent successful copies. These include stored records and queue metadata, not screenshot files or credentials. Extra/manual/off-host backups may exist and must be included in deletion handling |
| Host service logs | Retention depends on host logging configuration; the bot does not impose a fixed log-expiration period |

A startup history scan normally examines the previous 72 hours in the configured submissions channel and recorded DM sessions. This is a discovery/retry window, **not** an automatic deletion schedule. Successful partial submissions are completed jobs and are not automatically re-read to fill missing fields. Deleting an original upload does not automatically delete scores, cached copies, audit attachments or backups.

The operator must remove data when it is no longer needed, when a valid deletion request applies, or when otherwise required by law or Discord. The absence of a built-in purge is not permission to retain data forever. When service ends, the operator must handle remaining stored Discord data consistently with those requirements.

## 5. Your choices and privacy requests

You can stop submitting, remove an original message where Discord permits, or stop using the bot. Request access to your stored records, correction of inaccurate data, or deletion through the private route in Section 1. The operator may verify the request through the Discord account concerned and request only information reasonably needed to locate and verify it. Do not send identity documents or account passwords.

Requests are handled promptly and within any applicable legal deadlines. The current bot has no automated full-data-deletion command. /admin-remove removes numeric leaderboard scores but does not erase aliases, submissions, moderator logs, cached/Discord image copies or backups. A full request therefore requires operator handling across the affected stores, bot-authored messages and copies under the operator's control.

Deletion requests also need protection against reimport through pending jobs, history recovery or restored backups. The operator should stop relevant processing, remove or rebuild affected copies as required, and apply the deletion again before any restored data is put back into use. If retention is legally required, the operator will explain the applicable limit where permitted and restrict the retained information to that purpose. Routine troubleshooting or convenience alone does not override a valid deletion requirement.

We cannot delete another person's independent copy or Discord's own retained data. We will address copies under the operator's control and explain where a request must instead be directed to Discord or a separate server/host operator. Applicable law may also provide rights to object, restrict processing, receive portable data, withdraw consent where processing relies on it, or complain to a competent supervisory authority; ask the operator about your situation.

## 6. Security, age and changes

Tokens belong in private configuration, and access to hosts, backups and audit channels should be restricted. No security system or network transmission can be guaranteed. Report suspected unauthorized access privately through [SECURITY.md](SECURITY.md). The operator must assess incidents and provide any notifications required by law and Discord.

The bots are not intended for users below Discord's minimum age or the higher minimum required in their jurisdiction. Do not submit information about someone who is ineligible. Report suspected ineligible-user data to the operator for review and appropriate deletion.

Updates will appear here with a revised date. Material changes to data use or disclosure will be communicated through the relevant server/application where appropriate, with any legally required choice or authorization before the new processing begins.
