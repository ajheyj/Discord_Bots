# Validation results

The sections below record results at each development stage. The latest automated suite has 84 tests (79 pass and five private-image cases skip without fixtures) on the build Linux environment. Earlier counts and guide-length measurements are historical. Current setup instructions are in [INSTALL.md](INSTALL.md), and behavior is described in [README.md](README.md).

Tested in the build environment with Python 3.12, discord.py 2.7.1 and installed Tesseract. No live Discord credentials were supplied.

| Input/check | Result |
|---|---|
| Original direct screenshot | Accepted: 4,619 packs, $26.7Qa, 229 coins |
| Original monitor photo | Accepted: 2,986 packs, $1.93Qi, 859 coins |
| Direct screenshot converted to quality-65 JPEG | Accepted with the same values |
| Half-size, quality-65 JPEG | Rejected: money did not meet agreement/confidence requirements |
| 350×146 heavily blurred image | Rejected |
| Blank image | Rejected |
| Large money values differing by 1 | Sorted correctly without float rounding |
| Older submission | Independent higher scores retained |
| Failed submission | Scores unchanged; audit recorded |
| Database reopen | Player records retained |
| Python compilation and slash command definition loading | Passed |
| Unit tests | 3 passed |
| Discord pin guide | 1,453 characters; fits one ordinary 2,000-character message |

Not tested: live Discord reactions/permissions/pins/reconnects, real concurrent submissions, Windows execution, Linux systemd operation, Docker builds or deployment to cloud providers. The deployment files are supplied for installation and live verification; they are not claimed to be deployed. No universal OCR success rate can be established from two original examples. The half-size rejection is an intentional conservative failure, not proof that every low-resolution screenshot will fail. More varied player screenshots should be tested before launch.

## Historical admin correction validation

14 tests pass (3 existing + 11 new) under the build environment. New checks cover strict exact number parsing, single-category lowering, preserved other stats/submission history/board IDs, confirmed removal, audit history, migration/reopen, score rollback on audit failure, invalid inputs, Manage Server and configured-server checks, private responses, cancellation and display refresh failure after a successful save. Live Discord commands and deployment still need testing on the running server. See INSTALL.md.

## Historical role and audit validation

23 automated tests pass (14 existing + 9 new). Role membership, audit embeds, durable retries, save behavior on delivery failures, atomic outbox insertion and database migration are covered. See INSTALL.md for the test scope and live Discord checks still required.

## Historical OCR panel fallback validation

34 tests discovered: 33 passed and 1 skipped with available private samples. The new monitor photo and original direct screenshot return their exact expected values. The cached older monitor photo is truncated and was explicitly skipped. Default installs without private samples skip three optional image tests (31 pass, 3 skip). See INSTALL.md.

## Startup history recovery and failure reporting

52 tests discovered: 49 pass, 3 optional private-image tests skip without OCR_SAMPLE_DIR. The 18 new tests cover history filtering/backpressure/deduplication, worker replay behavior, original-message failure embeds, retry/deduplication after restart, and atomic failure recording. Prior role/admin/OCR tests still pass. Live Discord history and audit channel permissions need server-side checks. See INSTALL.md.

## Reported live checks

The operator reported successful Debian-container bot startup, a screenshot updating the boards, admin correction/audit channel delivery, and the formerly rejected monitor photo passing after the OCR change. This does not verify all history-recovery edge cases, every role-permission combination or the Windows/Docker/cloud deployments. Documentation consolidation changes no runtime code and did not rerun the application suite.

## Player Stats layout, identity and optional metrics

Built from ac0bd6e. With both private sample directories enabled: **71 discovered, 70 passed, 1 skipped** (the cached earlier monitor photo is truncated). Without the private image environment variables: **71 discovered, 66 passed, 5 skipped**. No live Discord token was used for this update.

Both new original images read `CROSSBAR_CHRIS`, $34.7Qi, 986 coins and 6 shiny cards; the top view also reads 9,057 packs and the scrolled view reads 294090 seconds (03d 09h 41m 30s). A panel crop also passed exactly; a 75%-size version was conservatively rejected for uncertain money text. Reduced-resolution success is not guaranteed. Legacy direct and available monitor-photo regressions also pass. The old corrupted fixture remains explicitly skipped rather than repaired or accepted.

Tests cover Discord-keyed identity across Epic renames, same-name/different-Discord separation, name history, preventing name rollback from older message replay, nullable missing metrics, preserved maxima, exact money values, additive legacy-schema migration/reopen, transaction rollback on a profile write failure, shiny/playtime admin corrections, time parsing/unit bounds, mixed-name rejection, and two-view worker processing without partial saves. Existing roles/audit/replay/OCR tests remain passing. New command definitions load locally with five categories and missing-value/time formatting.

The UI, usernames and label handling remain OCR heuristics, not verified Epic account linking. Confidence/consistency checks can reject clear inputs or repeat the same error. Live five-board creation/pins, production migration/permissions and broad device coverage need server-side verification. Docker copies the new module but a Docker build was not run. Schema rollback requires the matching pre-upgrade database, not just old code.

## Durable queue and resource controls

Built from the deployed Player Stats source at **90ed33c**. Linux automated suite: **84 discovered, 79 passed, 5 optional image tests skipped**. Prior in-memory worker tests were replaced with durable-stage tests; roles, identity, admin edits, audits, history filtering, numeric parsing and existing OCR checks remain covered. No live Discord credentials were used.

The burst test admits **500 distinct users, two synthetic small files each**, interrupts processing at job 125, closes/reopens the database, resumes work, injects temporary download and OCR errors, and deliberately makes every 17th input unreadable. Every accepted job reaches a terminal state: **471 done, 29 failed**, with one OCR coroutine and no more than two downloads active. It verifies original job/user IDs, no duplicate scores, bounded concurrency, retained attempt counts, file cleanup and released storage reservations. It uses fake Discord and fake OCR: it is not a real 1,000-photo throughput, RAM, CPU or Discord-rate-limit benchmark.

Separate subprocess checks verify OMP/OpenCV/BLAS limits are each one and an OCR timeout kills both the parent runner and its descendant process on Linux. Real paired new-layout screenshots also pass through the actual isolated/single-thread runner with `CROSSBAR_CHRIS`, 9,057 packs, $34.7Qi, 986 coins, 6 shiny cards and 294090 playtime seconds. That real-image check is additional to the default suite's skipped private-image fixtures.

Other checks cover committed admission before acknowledgment, duplicate IDs, global/per-user/storage/free-space rejection, persistent stage recovery, finite retry/backoff budgets, crash attempts not resetting budgets, atomic score/job completion rollback, successful-message/admin-correction protection, cached-image processing after source deletion, unchanged-attachment enforcement, partial-download reuse, reaction failures not undoing scores, failure retention cleanup, same-database instance locks, WAL-aware backup integrity/retention and rejection of unsafe storage directories or nonpersistent databases.

Not live-tested: Discord backlog/rate limits, production permissions, queued-reaction delivery, real 500-user traffic, Windows process-tree termination, Docker/cloud deployment, off-host disaster recovery or the full range of image sizes. Cache reservations and backup retention do not guarantee capacity under arbitrary host/disk failures. Automatic DB backups exclude image spools; full recovery of originals deleted from Discord needs a stopped data-directory/volume backup. See [INSTALL.md](INSTALL.md).

## November 14: partial recognition and private DM submissions

Linux suite: **100 discovered, 95 passed, 5 optional private-image fixtures skipped**. Includes the 500-job restart/retry simulation. No live Discord token was used.

The supplied November 14 screenshots passed the actual single-thread OCR runner, individually and together. Both provide CROSSBAR_CHRIS, money 82,200,000,000,000,000,000 ($82.2Qi) and grade coins 1,238. The 14.08.29 view also reads packs 10,169 and conservatively omits its clipped shiny row; the 14.08.05 view reads shiny cards 8 and omits its clipped packs row. Their paired result includes all four numeric stats. Playtime is absent and therefore omitted, preserving any saved value. New Stats/Settings tabs no longer require rejecting otherwise readable rows. Private images are excluded from the update ZIP/repository.

New tests verify independent partial-field acceptance, rejection when no stat is confident, supported-number conflicts remaining omitted, usable-image preservation when another image fails, exact committed before/after snapshots, unchanged/lower/missing values, name chronology, matched-name protection, ephemeral command replies, blocked DMs, private user-scoped result retrieval, session expiry, DM-channel download metadata, missed-DM startup history, notification retries, no new public replies/reactions and cached screenshot copies in audit delivery. Existing queue/backup/role/admin/identity tests remain passing after updating expectations for partial recognition and private delivery.

Not live-verified: actual Discord command sync, DM privacy settings, attachment permissions/limits, API rate limits, production database migration, Windows and Docker. Network ambiguity can duplicate a DM/audit message; scores remain idempotent. Screenshots can be unavailable after cache eviction/expiry, and DM jump links cannot be opened by moderators. Audit channel permissions remain the operator's responsibility. Earlier test sections describe historical versions; this section is the current behavior.

## November 14: Money Earned fallback

Current Linux suite: **108 discovered, 103 passed, 5 optional private-image cases skipped**. Eight new tests cover fallback invocation, agreement, conflicting supported numbers/suffixes, unknown suffixes, single-reading rejection, confidence filtering and absence of a character whitelist.

The reported Discord result confirms Money Earned was omitted rather than merely unchanged; the prior $82.2Qi remains saved. The exact attached screenshot reads correctly with Tesseract 5.5.0 in the development environment, so the production-specific confidence failure is not reproduced. The patch adds six bounded, unrestricted alternative OCR passes only when the initial passes provide fewer than two valid agreeing reads. Existing supported-number disagreements cannot be rescued by majority voting. Failures report whether readings conflicted or how many valid high-confidence readings were available.

Real money-crop validation forced every original OCR reading unavailable; the fallback still recovered exactly 82,200,000,000,000,000,000 ($82.2Qi) using agreeing accepted reads. Full-image extraction also remains correct. This demonstrates an additional recovery path, not a guarantee for every production engine/image. No digits or suffixes are guessed or rewritten; confidence remains at least 65. No live Discord token was used. After deployment, resend the screenshot: an already completed partial submission is not automatically reprocessed.
