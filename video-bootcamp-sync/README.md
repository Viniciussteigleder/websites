# video-bootcamp-sync

Proof-of-concept tool to pull videos + prompt material from the
`aivideobootcamp` Skool community into Google Drive
(`_03-Privat/03_AI/01-Video/`).

See [PLAN.md](./PLAN.md) for the architecture and, importantly, the
**live test results**: Drive upload and video download were both proven
working end-to-end in this session; browser-based lesson mapping could
not be tested here (this sandbox blocks outbound browser traffic
entirely, not a Skool-specific issue) but a lighter cookie-based JSON
approach (`skool_http.py`) was found and can complete that test today if
you provide a session cookie, or run locally later.

Quick start once you're ready to run it:

```bash
pip install -r requirements.txt
playwright install chromium
cp .env.example .env   # already points at your 01-Video folder
# put a Drive OAuth "Desktop app" credentials.json here (see PLAN.md)
python skool_sync.py --list-only   # sanity check: just list lessons found
python skool_sync.py               # full run: download + upload
```
