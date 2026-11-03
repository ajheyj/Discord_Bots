# Screenshot Leaderboard Bot

Start with **INSTALL.md**. Copy **SCREENSHOT_GUIDE.md** into a Discord message and pin it in #leaderboard-submissions.

One Python bot, with Windows, Linux/Proxmox and Docker/cloud deployment options. It watches one configured server and submissions channel; processes one uploaded image per message; records independent lifetime bests for packs, money and grade coins; edits three pinned Top 10 embeds; provides private /rank and paginated /leaderboard commands. Ties share a rank and are ordered by Discord user ID within ties. All players remain stored.

✅ means all three scores were read and saved, including an older screenshot that changes nothing. ❌ means the submission failed. ⏳ means queued/processing. A display update failure after a successful database save does not invalidate the score: the periodic refresh retries every two minutes. Discord outages can prevent reactions from appearing.

## OCR and numeric rules

Local Tesseract OCR uses whole-image text detection, fuzzy labels and four image variants. It requires at least two matching readings per statistic and rejects conflicting supported readings. It has no fixed screenshot coordinates and no paid vision API. Confidence and agreement reduce errors; they cannot guarantee accuracy or detect edited screenshots. Scores belong to the Discord uploader, not a verified Fortnite account. Use a trusted community or human moderation for prize competitions.

Configured suffixes: K=10³, M=10⁶, B=10⁹, T=10¹², Qa=10¹⁵, Qi=10¹⁸. These are conventional mappings inferred for this game, **not verified with the game developer**. Verify before running a real competition. Unknown suffixes fail; extend SUFFIXES in ocr.py only after confirming a game's convention. Exact integers, not floating point or SQLite numeric sorting, preserve large-money rankings. Display rounds money to three decimals; stored scores are exact to the screenshot's displayed precision. Hidden precision in abbreviated game values cannot be recovered.

## Data and operation

SQLite stores scores, persistent leaderboard message IDs and an audit of message ID/link, user ID, extracted values or failure, and UTC timestamp. Images are processed in memory and are not archived. The original Discord message must remain available if you want to inspect it later. Database contains community activity; restrict access and back it up.

One instance per server/database. A bounded queue (50 messages) and one OCR worker prevent simultaneous OCR jobs. Messages posted while the bot is offline, queued jobs lost on restart, and message edits are not replayed: players should repost when the bot is back. The bot automatically reconnects through discord.py. It restores missing leaderboard messages on refresh. Tokens belong in .env only.

Members with the configured ADMIN_ROLE_ID (or Manage Server permission if unset) can use /admin-set to correct one existing score and /admin-remove to remove a player from all rankings (explicit confirmation required). Every edit requires a reason and is recorded in the admin_audit table with the moderator, player, UTC time and old/new values. See ADMIN_UPDATE.md for usage and upgrade instructions. Removal is not a ban: later screenshots, including already queued submissions, can add the player again or raise a corrected score. Do not delete the database casually; it contains everyone's records.

## Development checks

Run `python -m unittest discover -s tests -v`. Run `python ocr.py "path/to/image.png"` to test a screenshot without Discord. No bot token is needed for these checks. See TEST_RESULTS.md for the tested samples and remaining limits.

## Sources

- [discord.py intents](https://discordpy.readthedocs.io/en/stable/intents.html)
- [discord.py interactions](https://discordpy.readthedocs.io/en/stable/interactions/api.html)
- [Tesseract installation](https://tesseract-ocr.github.io/tessdoc/Installation.html)
- [Discord Developer Portal](https://discord.com/developers/applications)

## Configurable moderator role and audit channel

Set ADMIN_ROLE_ID and AUDIT_CHANNEL_ID in your local .env to use an existing moderator role and private audit text channel. No roles or channels are created. See ROLE_AUDIT_SETUP.md for Discord command visibility permissions, durable delivery and installation. The configured role is required even for administrators. Leave the settings unset/0 to preserve Manage Server access and disable channel delivery.
