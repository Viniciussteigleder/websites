# AI Video Bootcamp → Drive Sync: Plan

## Goal

Pull course videos and prompt/text material out of the private Skool
community **aivideobootcamp** (skool.com/aivideobootcamp) and organize them
into your Google Drive at:

```
_03-Privat/03_AI/01-Video/<Module>/<Lesson>/
    video.mp4
    prompts.md
```

## Status of this pass (Proof of Concept)

This session produced:

1. This plan.
2. A runnable script scaffold (`skool_sync.py` + `drive_upload.py`) that
   implements the full pipeline end-to-end in code.
3. A **live Drive-side test**: the destination folder structure was
   created for real via the Drive API —
   `03_AI/01-Video/00_POC-test/01-Module-Example/prompts.md` — proving the
   folder-mapping and write access work. Delete `00_POC-test/` whenever;
   it's just the proof artifact.
4. What this pass could **not** test: the Skool scraping half. Skool is
   fully login-gated (confirmed — `/classroom` redirects to a login wall,
   no public preview), and the classroom DOM structure is unknown to me
   until someone with an active $9/mo membership logs in. That part is
   designed but unverified — expect to spend the first real run adjusting
   CSS selectors in `CONFIG` at the top of `skool_sync.py` after inspecting
   the actual page (open DevTools while logged in, or set `HEADLESS=False`
   and eyeball it).

## Why this can't run unattended from this session

- Skool requires an authenticated browser session tied to your paid
  account. I have no way to log in as you, and pasting a password into
  chat is a bad idea regardless.
- Even with cookies, video is very likely served through a third-party
  embed (Wistia/Vimeo/similar) with signed, expiring URLs — not a plain
  `<video src>` — so the extraction logic has to run in a real browser
  context, not a simple HTTP scraper.

So the design below is a **script you run locally**, where you log into
Skool yourself once in a real Chrome window. Nothing about your Skool
credentials touches this repo or this chat.

## Architecture

```
skool_sync.py           orchestrator: Playwright browser, login wait,
                         classroom crawl, per-lesson extraction, download
drive_upload.py          Google Drive API v3 upload, idempotent
                         (checks for existing folder/file by name+parent
                         before creating — safe to re-run)
requirements.txt
.env.example              SKOOL_COMMUNITY=aivideobootcamp
                           DRIVE_ROOT_FOLDER_ID=1GxC-iV9tKokCthsiCQrq0UM7QmxOrOBz
```

### Flow

1. **Login (one-time, interactive).** Playwright launches a real,
   visible Chromium window using a persistent profile directory
   (`.playwright-profile/`), so the login session is cached on disk
   between runs — you only log in once.
2. **Crawl classroom.** Navigate to
   `skool.com/aivideobootcamp/classroom`, enumerate the module/category
   sidebar, then each lesson within a module.
3. **Per lesson, extract:**
   - Title → used for the Drive subfolder name.
   - Video → detect `<video>` tag or known embed iframe
     (Wistia/Vimeo/YouTube). Hand off to `yt-dlp` for the actual
     download since it already knows how to pull signed/streamed video
     from all of those hosts.
   - Prompt/text material → the lesson body text (Skool lesson pages are
     usually a rich-text description below the video) saved as
     `prompts.md`.
4. **Download locally** to `./downloads/<Module>/<Lesson>/`.
5. **Upload to Drive**, mirroring that same tree under
   `03_AI/01-Video/`, reusing folders that already exist so re-runs are
   incremental (only new/changed lessons get uploaded).

## Setup (for when you're ready to run it for real)

1. `pip install -r requirements.txt && playwright install chromium`
2. Google Cloud: create an OAuth Desktop client, enable the Drive API,
   download `credentials.json` into this folder (gitignored).
3. `cp .env.example .env` and fill in `DRIVE_ROOT_FOLDER_ID` (defaults to
   your `01-Video` folder id, already filled in below).
4. `python skool_sync.py` — a Chrome window opens; log into Skool
   manually when prompted; the script waits for you, then proceeds
   automatically from there.
5. First run: expect to fix 1-2 CSS selectors in `CONFIG` once you can
   see the real classroom DOM. Leave `HEADLESS=False` for this.

## Open risks / things to decide before the real run

- **ToS.** Skool's terms generally prohibit automated scraping.
  Downloading content you're already paying for, for your own offline
  backup, is a common and low-risk use of a tool like this, but
  redistributing it or running it at high frequency/volume is a
  different story and could get the account flagged. Treat this as a
  personal-archive tool, run it occasionally, not a background sync
  job.
- **Video hosting unknown.** If Skool serves video through something
  `yt-dlp` doesn't support out of the box, the download step needs a
  fallback (e.g., capturing the network request for the `.m3u8`/`.mp4`
  manifest directly via Playwright's request interception). The script
  has a stub for this (`extract_video_via_network()`), untested.
- **Rate/volume.** No estimate yet of how many modules/lessons exist —
  that's only visible after login. Worth doing a dry run listing titles
  only (`--list-only` flag) before downloading everything.

## Next step

Run this locally once to log in and let it inspect the real classroom
DOM, or hand this repo + the actual class URLs to the more capable model
you mentioned switching to, and it can tighten the selectors and do the
first real sync.
