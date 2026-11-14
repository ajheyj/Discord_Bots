# Security policy

## Report privately

Do not open a public issue containing a vulnerability exploit, credentials, private images or user records. If this repository offers GitHub's **Report a vulnerability** option under its Security tab, use that private route. Otherwise contact the bot operator privately through the server owner/moderators, asking for the maintainer's direct private security contact. See [SUPPORT.md](SUPPORT.md). Do not assume GitHub private vulnerability reporting is enabled.

Describe the affected bot/version, impact and minimal reproduction steps. Use a test account/server where possible. Do not access another person's data, disrupt the live service or publish sensitive evidence. There is no advertised bug-bounty program or blanket authorization to test production systems.

## Credentials and personal data

Keep bot tokens, .env files, database/spool directories, backups and private screenshot fixtures out of commits and public issues. If a token is exposed, reset it in the Discord Developer Portal promptly and update the deployed secret. Removing the visible file or Git commit alone does not invalidate a token.

Restrict host/data-directory access and audit-channel permissions. Enable only the Discord permissions/intents needed for the selected features; the leaderboard does not need Administrator. Audit image copies need Attach Files permission and access limited to intended viewers.

Maintain supported dependencies, persistent backups and a tested restoration procedure. Do not silently substitute an old database during rollback: schema compatibility and privacy deletions must both be preserved.

## Incident handling

Operators should contain an incident, preserve only necessary restricted evidence, determine affected data/users, rotate compromised credentials and correct the cause. Notify Discord and affected users when required by Discord's developer terms or applicable law. Do not conceal an incident or publish user records while investigating it.

Changes are maintained against the current documented code; no fixed long-term support window is promised for older versions. Report problems even if you are unsure whether they affect the latest release.
