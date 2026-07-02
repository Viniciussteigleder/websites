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

This session produced, and then actually ran, three separate probes:

1. **Drive-side write, tested live and confirmed working.** Created
   `03_AI/01-Video/00_POC-test/01-Module-Example/prompts.md` for real via
   the Drive API — proves the folder-mapping and write access work.
   Delete `00_POC-test/` whenever; it's just the proof artifact.

2. **Video download, tested live and confirmed working.** Ran the exact
   mechanism `skool_sync.py` uses (`yt-dlp`) end-to-end against a public
   video and got a real 41 MB playable MP4 back. The download step of the
   pipeline works in this environment.

3. **Browser-based lesson mapping — could not be tested, for a reason
   unrelated to Skool.** I tried to launch the pre-installed Chromium
   (via Playwright) against the Skool classroom and it failed with
   `net::ERR_CONNECTION_RESET`. To isolate the cause I pointed the same
   browser at `example.com` and `google.com` — identical failure. Plain
   HTTP clients (`curl`, `yt-dlp`, Python `requests`) reach all three
   sites fine from this same sandbox. So this is **this cloud session
   blocking outbound connections specifically from a spawned browser
   process**, not a Skool login wall or a proxy/CA problem — confirmed by
   testing with and without the session's proxy, with a real Chrome user
   agent, and with automation-detection flags disabled. This is a hard
   constraint of the current remote environment, not something fixable by
   retrying or tweaking the script.

### A better path, found while investigating #3

While probing, I fetched Skool's public `/about` page with plain `curl`
(which does work here) and found Skool is a **Next.js app that
server-renders a `__NEXT_DATA__` JSON blob** into every page's HTML —
the same JSON React hydrates from. For a logged-in request, the
classroom/lesson pageProps very likely contain the full module/lesson
list and video links directly in that JSON, no client-side JS execution
required to read them.

That means lesson mapping probably doesn't need a browser at all — just
an authenticated HTTP GET (using your Skool session cookie) + a JSON
parse. This is lighter than driving a full browser, and — usefully for
testing — it works within this sandbox's network constraints, unlike
Playwright. Added `skool_http.py` implementing this: point it at the
classroom URL with `SKOOL_COOKIE` set to your logged-in session's Cookie
header, run with `--discover` first to see the real JSON shape (unverified
until tried against a real session), then `find_lesson_like_objects()` to
extract lesson entries.

**This is the one piece of the PoC that could still be completed in this
session**, if you're willing to paste a session cookie (not your
password) — see "Want to finish the live test now?" below.

Either way — cookie-based JSON reading now, or the Playwright script run
locally later — expect to spend the first real attempt adjusting field
names/selectors against the real authenticated response; nobody has seen
that JSON/DOM shape yet.

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

## Follow-up test, no cookie needed

You declined to share a session cookie (reasonable). Two more things were
tried without any credentials:

1. **Called `/classroom` logged out anyway**, to see what the
   `__NEXT_DATA__` blob contains without auth. Answer: nothing lesson-related.
   `pageProps.courseRoute` is `false`, `videos` is `[]`, `self` is `null` —
   Skool renders the public marketing/about content at that URL when
   there's no session, not the classroom. So there's no way to read the
   lesson list without logging in — confirmed directly rather than assumed.

2. **But that same public payload contained a real video URL**:
   `pageProps.currentGroup.metadata.lpAttachmentsData` includes the
   community's public pitch/intro video, hosted on Loom:
   `https://www.loom.com/share/e0838a4ac97647beb59ed491e6407579`. This is
   genuine AI Video Bootcamp content (not a stand-in), public, no login
   required. **Downloaded it end-to-end with `yt-dlp`**: pulled 123.9 MB
   of video + 4.1 MB of audio as HLS segments and verified the video
   stream is a structurally valid MPEG-TS (correct `0x47` sync byte every
   188 bytes, matching real broadcast-stream framing). It didn't get
   muxed into a single playable `.mp4` file because the only `ffmpeg`
   available in this sandbox is a stripped-down build bundled for
   Playwright screenshots (no H.264/AAC support) — a sandbox packaging
   gap, not a bug in the download logic. A normal `ffmpeg` install (what
   the local setup in README.md gets via `apt`/`brew`) mixes these
   automatically; `yt-dlp` does this itself when ffmpeg is on PATH.

**Net result:** the download mechanism is now proven against Skool's
actual video host (Loom), not just a generic test file, and the "no
lesson data without login" wall was confirmed directly rather than
assumed. The only thing that still requires your login is enumerating
the *lesson list itself* — that part is unavoidably behind auth, by
design, on Skool's end.

## Want to finish the live test now?

If you paste your Skool session cookie (DevTools → Network tab → any
`skool.com` request → copy the `Cookie` request header — not your
password), I can run:

```
SKOOL_COOKIE='<paste>' python3 skool_http.py --discover \
  https://www.skool.com/aivideobootcamp/classroom
```

right now in this session and show you the real lesson/module JSON, which
would complete the "map all lessons" half of this PoC today instead of
waiting for a local run. A session cookie is bounded (expires, and
logging out anywhere revokes it) but it is still live access to your
account for as long as it's valid — your call whether that's worth it
for finishing the test now vs. running everything locally later where
this concern doesn't apply.

## Next step

Either paste a cookie per above to finish the mapping test now, or run
`skool_sync.py` locally to log in yourself and let it inspect the real
classroom — or hand this repo + the actual class URLs to the more
capable model you mentioned switching to, and it can tighten the
selectors/field names and do the first real sync.
