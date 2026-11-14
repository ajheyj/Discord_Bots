# Discord Bots

Discord bots maintained by [ajheyj](https://github.com/ajheyj) for a general community of friends. This repository currently contains one bot. More bots can be added as separate projects without changing the purpose of the repository.

## Available bots

| Bot | What it does | Documentation |
|---|---|---|
| Screenshot Leaderboard | Reads game-stat screenshots with local Tesseract OCR and maintains Discord-account-based lifetime leaderboards for packs, money, grade coins, shiny cards and playtime. | [Overview](leaderboard_bot/README.md) · [Installation](leaderboard_bot/INSTALL.md) · [Player guide](leaderboard_bot/SCREENSHOT_GUIDE.md) |

The repository is for the whole Discord community; individual bots may support specific games or activities. An idea or roadmap item is not an available bot. New bots will be listed here when their code and documentation are added.

## Using the leaderboard bot

1. Run **/submit** in the server where the bot is installed.
2. Read the private instructions and send one or two screenshots to the bot in DMs.
3. Receive a private result summary. Each confidently read stat can update independently; unreadable fields stay unchanged and lifetime bests never decrease.
4. Use **/submission-result**, **/rank** or **/leaderboard** for private results and standings. Public leaderboard messages remain visible to the server.

Screenshots and submission summaries may be copied to the configured moderator audit channel. A DM submission is private from ordinary server members, not from the bot operator and authorized audit-channel viewers. Read the [Privacy Policy](PRIVACY.md) before submitting. The bot does not verify Epic account ownership or image authenticity.

## Install or host a bot

Open the selected bot's installation guide. The leaderboard supports Python/Tesseract hosting on Windows or Linux, including a Debian guest on Proxmox, and a Docker configuration for compatible hosts. An independently hosted copy needs its own Discord application/token, configuration and persistent storage. Platform support does not mean every environment has been live-tested.

Never upload bot tokens, `.env`, databases, image caches, backups or private user screenshots to this repository. Do not overwrite a working `.env` with an example file. Back up persistent data before updating and follow the bot's migration instructions. Use the tests documented for the version you deploy.

## Shared documents

| Document | Purpose |
|---|---|
| [Terms of Service](TERMS.md) | Rules for using the maintainer-operated bots and service limitations |
| [Privacy Policy](PRIVACY.md) | Data collection, screenshot visibility, storage, retention and deletion requests |
| [Support](SUPPORT.md) | Help, private privacy requests and useful bug-report details |
| [Security](SECURITY.md) | Reporting vulnerabilities and protecting credentials |
| [Operator guide](OPERATOR_GUIDE.md) | Publishing policy links, permissions, retention and handling privacy requests |
| [Contributing](CONTRIBUTING.md) | Proposing changes and adding another bot |

These shared policies cover the maintainer-operated services identified by their application/server profiles and their documented features. Independent hosts operate their own services and must supply accurate operator/contact/privacy information. A new bot must have its actual data practices documented before it is enabled; the policy does not authorize unspecified future collection.

## Support and privacy requests

For a hosted bot, contact its operator privately through the server owner or moderators. They can route your request to the bot operator. Include the bot name and your Discord account ID; never send passwords or bot tokens. Full instructions are in [SUPPORT.md](SUPPORT.md). Public GitHub issues are appropriate for nonsensitive software bugs, not private screenshot evidence or personal-data requests.

## Development

Keep each bot in its own folder with an overview, install guide, example configuration and relevant tests. Shared documents live at the repository root. Contributions should minimize data collection, preserve existing user data during upgrades, and make permissions and public/private responses clear.

No repository-wide software license is currently selected. Public source visibility does not itself grant an open-source license. The service Terms do not license the source code; existing third-party dependency licenses continue to apply.

These projects are independently maintained and are not endorsed by Discord, Epic Games or other referenced platforms or game publishers. Trademarks belong to their respective owners.
