# Discord OCR Leaderboard — improvement roadmap

Saved November 2, 2026. These are proposed future improvements unless marked otherwise; they are not promises that the running bot already includes them.

| Priority | Improvement | Purpose and acceptance criteria | Status |
|---|---|---|---|
| 1 | Automatic database backups | SQLite backup API, integrity check and daily retention are implemented; test full disaster recovery and keep an off-host copy. Database backups do not include cached images. | Implemented locally; production restore drill still needed |
| 2 | Recover pending screenshot submissions after restarts | SQLite-backed accepted jobs and temporary image spooling now resume beyond the history window. The 72-hour scan still discovers unaccepted/failed messages. Preserve the entire data directory for cached-image disaster recovery. | Implemented: persistent accepted jobs and startup history recovery |
| 3 | Specific failure explanations | Identify unreadable packs/money/coins, unsupported number suffixes, invalid files, temporary Discord/download/OCR engine errors, or database failures. Tell players whether to retake a photo or retry later. Private DM result summaries, partial recognition notes and matching moderator audit snapshots/screenshots are implemented. | Implemented locally; live Discord verification needed |
| 4 | Broader OCR regression testing | Build a consented/private collection of PC, console, mobile, cropped, compressed and monitor-photo cases. Check exact expected values and rejection of ambiguous images when changing preprocessing. Keep private screenshots out of the public repository by default. | Ongoing: automatic green-header panel detection and bright-text masking added for the newly reported photo; wider device coverage still needed |
| 5 | Submission cooldowns | Configurable per-user pending-job and global storage/capacity limits are implemented. Time-based cooldowns and strict per-user round-robin scheduling remain future work. | Partially implemented: admission limits |
| 6 | Review suspicious increases | Hold unusual changes for role-authorized human approval. Tune thresholds to realistic game progression and suffix precision; do not treat a large increase alone as proof of cheating. | Planned |
| 7 | Cross-account duplicate-image detection | Detect identical image bytes or perceptually similar uploads by different Discord users; flag for moderation. Similarity does not establish account ownership or forgery. | Planned |
| 8 | Admin undo | Reverse a specific audited correction/removal safely. Check intervening submissions and admin edits; require role permission, reason and an audit record for the reversal. | Planned |
| 9 | Moderator status command | /queue shows pending/job stage totals, oldest pending age, worker state, reserved space, last backup and last issue. Uptime, latency estimates and audit-delivery counts remain future work. | Partially implemented: /queue |

## Additional OCR correctness work

- Investigate disagreements involving unsupported suffix readings. Currently an unsupported token is discarded, so two matching supported reads can pass despite an additional unsupported reading. Consider treating credible unknown-suffix readings as uncertainty; validate against real examples before changing acceptance rules.
- Retain rejection when supported numeric readings conflict. Do not silently use a majority vote or automatically rewrite uncertain digits/suffixes.
- Preserve exact integer storage and verify any new game suffix before mapping it.
- Expand panel/label detection for future UI changes without fixed screenshot coordinates. Current fallback assumes a wide green header and light text; different colors/fonts may still require an update.

## Existing capabilities to preserve

Five all-time personal-best leaderboards (packs, money, coins, shiny cards and playtime); /rank and paginated /leaderboard; one or two matching Player Stats scroll views per submission; private /submit DM uploads and before/after result summaries; persistent scores; systemd operation on container 205; role-configured admin corrections/removals; durable admin audit-channel delivery. Admin overrides do not block a subsequent screenshot from raising the score or re-adding a removed user.

Suggested next work: verify the durable queue and backups on the running server, then improve monitoring, fairness and device-specific OCR coverage.

## Player Stats update implemented

The blue Player Stats layout now supplies an OCR username, optional off-screen fields, shiny-card counts and structured playtime. Permanent Discord user IDs own score rows; a mutable latest-observed Epic name and alias history do not create duplicate score records. Old-message replay cannot overwrite a name observed in a newer message. Matching two-view submissions merge per-category maxima atomically. Epic ownership and image capture time are not verified.

## Durable queue update implemented

Database-backed admission, private image spooling, two download workers, one isolated/single-thread OCR job, timeouts and limited retries, restart recovery, resource admission limits, batched boards, private /queue and consistent daily backups are implemented. The 500-job simulation validates state/concurrency behavior, not real-world OCR throughput or unlimited capacity.

## Private submissions and partial recognition update

/submit privately opens a 24-hour DM upload session. /submission-result privately shows the caller's latest completed result. New public processing replies/reactions are disabled. Individual readable stats save independently while uncertain/off-screen values remain unchanged; conflicting readable player names still reject a pair. Moderator audit summaries mirror committed changes and copy available screenshots within the channel upload limit. Startup recovery covers recorded DM sessions as well as legacy submissions-channel history.

## November 15 additions

A persistent pinned usage guide now precedes the scoreboards using bot-owned message slots. Whole-image label search supplements template geometry for varied/cropped/photo submissions. Download-size discrepancies validate decoded images and reserve their actual cache size while keeping original attachment IDs. OCR can still omit conflicting/unreadable fields; broader consented fixtures and runtime monitoring remain useful next steps.
