# Validation results

The sections below record results at each development stage. The latest automated suite has 71 tests (66 pass and five private-image cases skip without fixtures). Earlier counts and guide-length measurements are historical. Current setup instructions are in [INSTALL.md](INSTALL.md), and behavior is described in [README.md](README.md).

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
