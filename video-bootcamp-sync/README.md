# video-bootcamp-sync

Proof-of-concept tool to pull videos + prompt material from the
`aivideobootcamp` Skool community into Google Drive
(`_03-Privat/03_AI/01-Video/`).

See [PLAN.md](./PLAN.md) for the architecture, what was actually tested
in this pass (the Drive side, live), what wasn't (the Skool scraping
side — requires your login), and the known risks/open questions before
running this for real.

Quick start once you're ready to run it:

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # already points at your 01-Video folder
# put a Drive OAuth "Desktop app" credentials.json here (see PLAN.md)
python skool_sync.py --list-only   # sanity check: just list lessons found
python skool_sync.py               # full run: download + upload
```
