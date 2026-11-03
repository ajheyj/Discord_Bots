# Validation results

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

## Admin correction update

14 tests pass (3 existing + 11 new) under the build environment. New checks cover strict exact number parsing, single-category lowering, preserved other stats/submission history/board IDs, confirmed removal, audit history, migration/reopen, score rollback on audit failure, invalid inputs, Manage Server and configured-server checks, private responses, cancellation and display refresh failure after a successful save. Live Discord commands and deployment still need testing on the running server. See ADMIN_UPDATE.md.

## Configurable role and audit channel update

23 automated tests pass (14 existing + 9 new). Role membership, audit embeds, durable retries, save behavior on delivery failures, atomic outbox insertion and database migration are covered. See ROLE_AUDIT_SETUP.md for the test scope and live Discord checks still required.
