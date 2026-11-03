# Discord OCR Leaderboard — improvement roadmap

Saved November 2, 2026. These are proposed future improvements unless marked otherwise; they are not promises that the running bot already includes them.

| Priority | Improvement | Purpose and acceptance criteria | Status |
|---|---|---|---|
| 1 | Automatic database backups | Daily consistent SQLite backups, configurable retention, failure reporting, and a verified restore procedure. Prefer SQLite's backup API for live backups. Keep a copy outside the container for protection against host/disk loss. | Planned |
| 2 | Recover pending screenshot submissions after restarts | Startup scanning now retries failed/unprocessed messages posted in the previous configurable 72 hours, including offline uploads. Successful messages are skipped. Local durable job storage beyond the Discord history window and recovery outside that window remain future work. | Partially implemented: startup history recovery |
| 3 | Specific failure explanations | Identify unreadable packs/money/coins, unsupported number suffixes, invalid files, temporary Discord/download/OCR engine errors, or database failures. Tell players whether to retake a photo or retry later. Moderator audit-channel failure reasons with original-message links are now added; more specific player-facing replies remain future work. | Partially implemented: moderator failure reports |
| 4 | Broader OCR regression testing | Build a consented/private collection of PC, console, mobile, cropped, compressed and monitor-photo cases. Check exact expected values and rejection of ambiguous images when changing preprocessing. Keep private screenshots out of the public repository by default. | Ongoing: automatic green-header panel detection and bright-text masking added for the newly reported photo; wider device coverage still needed |
| 5 | Submission cooldowns | Per-user rate limits plus clear feedback and queue protection so one player cannot monopolize OCR processing. | Planned |
| 6 | Review suspicious increases | Hold unusual changes for role-authorized human approval. Tune thresholds to realistic game progression and suffix precision; do not treat a large increase alone as proof of cheating. | Planned |
| 7 | Cross-account duplicate-image detection | Detect identical image bytes or perceptually similar uploads by different Discord users; flag for moderation. Similarity does not establish account ownership or forgery. | Planned |
| 8 | Admin undo | Reverse a specific audited correction/removal safely. Check intervening submissions and admin edits; require role permission, reason and an audit record for the reversal. | Planned |
| 9 | Moderator status command | Show uptime, pending screenshot count, OCR worker health, last backup and queued audit deliveries. Do not disclose tokens or private data. | Planned |

## Additional OCR correctness work

- Investigate disagreements involving unsupported suffix readings. Currently an unsupported token is discarded, so two matching supported reads can pass despite an additional unsupported reading. Consider treating credible unknown-suffix readings as uncertainty; validate against real examples before changing acceptance rules.
- Retain rejection when supported numeric readings conflict. Do not silently use a majority vote or automatically rewrite uncertain digits/suffixes.
- Preserve exact integer storage and verify any new game suffix before mapping it.
- Expand panel/label detection for future UI changes without fixed screenshot coordinates. Current fallback assumes a wide green header and light text; different colors/fonts may still require an update.

## Existing capabilities to preserve

Three all-time personal-best leaderboards; /rank and paginated /leaderboard; one uploaded image per submission; success/failure/processing reactions; persistent scores; systemd operation on container 205; role-configured admin corrections/removals; durable admin audit-channel delivery. Admin overrides do not block a subsequent screenshot from raising the score or re-adding a removed user.

Suggested next work after stabilizing OCR: automatic backups, then durable screenshot submission recovery.
