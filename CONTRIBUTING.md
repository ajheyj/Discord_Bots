# Contributing

Open a nonsensitive GitHub issue describing the problem or proposed feature before undertaking a large change. Small fixes can be proposed with a clear explanation and relevant validation. Do not use issues or pull requests for tokens, private screenshots, database contents or personal-data requests; see [SUPPORT.md](SUPPORT.md) and [SECURITY.md](SECURITY.md).

## Changes to an existing bot

Read its README, installation guide and tests. Preserve Discord-account identity, existing records, privacy boundaries and permission checks unless a deliberate reviewed change requires otherwise. Explain migrations, resource implications and any change to public/private output or data retention. Use narrowly scoped regression tests for meaningful behavior changes; describe what was actually tested and what remains unverified.

OCR fixtures must be consented and suitable for their intended visibility. Keep private samples out of the repository. Synthetic or suitably redacted data is preferable for committed tests. Do not weaken confidence checks solely to make one image pass.

## Adding a bot

Give each bot a separate descriptive directory. Include an overview, installation/run instructions, .env.example without secrets, necessary dependencies and relevant tests. Document what it reads, what it stores, which permissions it needs, what users see publicly or privately, and how users can request help or deletion.

Update the root bot catalog and the applicable Terms/Privacy scope before launch. Do not list unfinished concepts as available. Keep shared policy claims accurate across bots and use bot-specific supplements when behavior differs.

No repository-wide software license is selected yet. Discuss intended contribution/reuse terms with the maintainer before submitting code; these contribution instructions do not grant or imply an open-source license.
