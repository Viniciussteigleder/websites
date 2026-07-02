"""Cookie-based (no-browser) Skool reader.

Skool is a Next.js app: every page ships a server-rendered
<script id="__NEXT_DATA__"> blob containing the page's props as JSON. For
a logged-in request, the classroom/lesson pageProps very likely contain
the module/lesson list and video links directly, with no client-side JS
execution needed to see them.

This means lesson mapping may not need a browser (Playwright) at all —
a plain authenticated HTTP GET + JSON parse is lighter, faster, and
(unlike a headless browser) works from environments with restricted
outbound browser traffic.

Usage: export SKOOL_COOKIE (the raw `Cookie:` header value from your
logged-in browser session — DevTools > Network > any skool.com request
> copy the Cookie header), then run with --discover first to see the
real JSON shape before trusting find_lesson_like_objects()'s heuristics.
"""

from __future__ import annotations

import json
import re

import requests

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S
)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}


def make_session(cookie: str) -> requests.Session:
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    s.headers["Cookie"] = cookie
    return s


def fetch_next_data(session: requests.Session, url: str) -> dict:
    resp = session.get(url, timeout=20)
    resp.raise_for_status()
    m = NEXT_DATA_RE.search(resp.text)
    if not m:
        raise RuntimeError(f"No __NEXT_DATA__ blob found at {url} (logged in? redirected?)")
    return json.loads(m.group(1))


def discover(session: requests.Session, url: str):
    """Print pageProps keys + a JSON preview, to design real selectors from."""
    data = fetch_next_data(session, url)
    page_props = data.get("props", {}).get("pageProps", {})
    print("Top-level pageProps keys:", list(page_props.keys()))
    print(json.dumps(page_props, indent=2)[:4000])


def find_lesson_like_objects(node, path="") -> list[dict]:
    """Heuristic recursive scan for dicts that look like a lesson/video entry.

    A real implementation should replace this once discover() has shown the
    actual field names Skool uses (likely something like title/name +
    videoLink/video/url). Kept generic on purpose since the schema is
    unverified without a logged-in session.
    """
    found = []
    if isinstance(node, dict):
        keys = {k.lower() for k in node.keys()}
        has_title = any(k in keys for k in ("title", "name"))
        has_media = any(
            k in keys for k in ("videolink", "video", "videourl", "url", "link")
        )
        if has_title and has_media:
            found.append({"path": path, "data": node})
        for k, v in node.items():
            found.extend(find_lesson_like_objects(v, f"{path}.{k}"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found.extend(find_lesson_like_objects(v, f"{path}[{i}]"))
    return found


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="e.g. https://www.skool.com/aivideobootcamp/classroom")
    parser.add_argument("--discover", action="store_true", help="dump raw pageProps JSON")
    args = parser.parse_args()

    cookie = os.environ.get("SKOOL_COOKIE")
    if not cookie:
        raise SystemExit("Set SKOOL_COOKIE to your logged-in browser's Cookie header value.")

    sess = make_session(cookie)
    if args.discover:
        discover(sess, args.url)
    else:
        data = fetch_next_data(sess, args.url)
        lessons = find_lesson_like_objects(data.get("props", {}).get("pageProps", {}))
        print(f"Found {len(lessons)} lesson-like objects (heuristic match):")
        for l in lessons[:20]:
            print(" ", l["path"])
