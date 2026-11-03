# OCR panel detection fix

## Why the clear monitor photo failed

Reproduced with the current repository OCR code at commit 97d609a: the new photo failed with `Could not confidently read Packs Opened`. Whole-image sparse-text OCR fragmented the stat labels and numbers in the photographed scene. Human readability does not guarantee that Tesseract's full-image segmentation forms the right lines. The extra Shiny Cards row is not one of our requested labels and is ignored.

A diagnostic crop demonstrated that the text could be recovered. The new production fallback finds candidate wide green headers automatically (no hard-coded screenshot x/y coordinates), derives the panel crop from each header's position/size, masks bright neutral text against the colorful background and tries block-text OCR. The whole-image path runs first. Fallback readings still need at least two matching values per statistic, value confidence >=65 and no conflicting supported values across accepted readings. Unknown suffixes are not guessed. As before, repeated Tesseract reads are correlated and cannot prove correctness.

The fallback tries at most two candidate headers with three text masks each. It can take longer on difficult images. Header color thresholds and crop proportions are heuristics for this game's UI, not universal panel understanding. Significant UI/color changes can still cause rejection.

## Verified output

| Image | Result |
|---|---|
| Newly submitted monitor photo, image(20261103-025938).png | Accepted: packs 5,639; money $116Qi = 116000000000000000000; coins 1,478 |
| Original direct screenshot | Accepted: packs 4,619; money $26.7Qa; coins 229 |
| Original earlier monitor photo | Not rerun: cached sample bytes were truncated; its image-regression test was explicitly skipped. The successful whole-image path is unchanged. |
| Blank input | Rejected |

Local suite: **34 tests discovered, 33 passed and 1 skipped** when the private sample directory was supplied. Without private samples, expect **34 tests discovered, 31 passed and 3 skipped**. Sample images are not included in this public-code update; set OCR_SAMPLE_DIR to a directory containing the original filenames to run those optional tests. These results do not establish a general OCR success rate or confirm live Discord behavior on your installation.

## Files to upload to GitHub

Upload the archive contents into the same leaderboard_bot/ directory, replacing matching files. Keep tests/test_ocr_panel.py inside tests/. Your .env, scores, admin commands and Discord audit configuration are not replaced. ROADMAP.md preserves the proposed future improvements.

## Install inside Debian container 205

After uploading to GitHub:

```sh
systemctl stop leaderboard-bot
mkdir -p /root/leaderboard-backups
cp /opt/Discord_Bots/leaderboard_bot/data/leaderboard.sqlite3 /root/leaderboard-backups/leaderboard-$(date +%Y%m%d-%H%M%S).sqlite3
cd /opt/Discord_Bots
git pull --ff-only
cd leaderboard_bot
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
```

**Install the updated requirements:** this fix adds opencv-python-headless for local panel detection and text masking. It brings NumPy as a dependency. It uses no AI API or paid service. Do not skip the pip command or the fallback cannot run. No .env changes are needed.

If any command fails, inspect the error before continuing. After the tests pass (with the three optional sample tests skipped unless you supplied their files):

```sh
chown -R leaderboard:leaderboard /opt/Discord_Bots/leaderboard_bot
chmod 600 .env
systemctl start leaderboard-bot
systemctl status leaderboard-bot --no-pager
```

Repost the original failed photo as a **new message** in #leaderboard-submissions. Check the exact three recorded values before accepting the result. Existing messages are not reprocessed automatically. There is no need to submit altered scores or make admin edits to test it.

To test any image offline, run `.venv/bin/python ocr.py "/path/to/image.png"` from the bot folder. It prints the extracted integers or an error. Use the original Discord attachment for comparisons; compressed/re-saved copies may behave differently.

## Rollback

Stop the bot and restore the previous ocr.py and requirements.txt from your preceding Git revision. The pre-fix source used here is 97d609a. Leaving the added image-processing package installed does not change the old code's behavior. No database migration is involved in this fix. Back up your checkout before discarding local edits.
