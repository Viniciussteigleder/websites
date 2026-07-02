"""AI Video Bootcamp (Skool) -> Google Drive sync. Run locally.

Logs into Skool interactively (once, cached in a persistent browser
profile), crawls the classroom, downloads each lesson's video + prompt
text, then uploads the tree to Drive via drive_upload.py.

Selectors in CONFIG are best-effort guesses at Skool's classroom markup
and WILL need adjustment after a first look at the real, logged-in DOM
(run with HEADLESS=False and use DevTools). See PLAN.md.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import subprocess

from playwright.sync_api import sync_playwright

import drive_upload

COMMUNITY = os.environ.get("SKOOL_COMMUNITY", "aivideobootcamp")
DRIVE_ROOT_FOLDER_ID = os.environ.get(
    "DRIVE_ROOT_FOLDER_ID", "1GxC-iV9tKokCthsiCQrq0UM7QmxOrOBz"  # 03_AI/01-Video
)
DOWNLOAD_DIR = pathlib.Path(__file__).parent / "downloads"
PROFILE_DIR = pathlib.Path(__file__).parent / ".playwright-profile"
HEADLESS = False

# Best-effort selectors — verify/adjust against the real logged-in DOM.
CONFIG = {
    "classroom_url": f"https://www.skool.com/{COMMUNITY}/classroom",
    "module_selector": "[class*='classroom-module'], [class*='CategoryItem']",
    "lesson_link_selector": "a[href*='/classroom/']",
    "lesson_title_selector": "h1, [class*='lesson-title']",
    "lesson_body_selector": "[class*='lesson-content'], [class*='description']",
    "video_iframe_selector": "iframe[src*='wistia'], iframe[src*='vimeo'], iframe[src*='youtube']",
    "video_tag_selector": "video",
}


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_-]+", "-", text)[:80] or "untitled"


def wait_for_login(page):
    print("Log into Skool in the opened browser window...")
    page.goto(CONFIG["classroom_url"])
    page.wait_for_url(re.compile(r"/classroom"), timeout=0)
    print("Logged in, continuing.")


def list_lessons(page) -> list[dict]:
    """Return [{module, title, url}] by crawling the classroom sidebar.

    STUB: exact DOM traversal depends on Skool's real markup, which is
    only visible when authenticated. Adjust selectors in CONFIG, then
    this function, after inspecting a live logged-in session.
    """
    page.goto(CONFIG["classroom_url"])
    page.wait_for_selector(CONFIG["lesson_link_selector"], timeout=15000)
    lessons = []
    links = page.query_selector_all(CONFIG["lesson_link_selector"])
    for link in links:
        href = link.get_attribute("href") or ""
        title = (link.inner_text() or "").strip()
        if title and href:
            lessons.append({"module": "General", "title": title, "url": href})
    return lessons


def extract_lesson(page, lesson: dict) -> dict:
    page.goto(lesson["url"])
    page.wait_for_load_state("networkidle")

    title_el = page.query_selector(CONFIG["lesson_title_selector"])
    title = title_el.inner_text().strip() if title_el else lesson["title"]

    body_el = page.query_selector(CONFIG["lesson_body_selector"])
    body_text = body_el.inner_text().strip() if body_el else ""

    video_url = None
    iframe = page.query_selector(CONFIG["video_iframe_selector"])
    if iframe:
        video_url = iframe.get_attribute("src")
    else:
        video_tag = page.query_selector(CONFIG["video_tag_selector"])
        if video_tag:
            video_url = video_tag.get_attribute("src")

    return {
        "module": lesson["module"],
        "title": title,
        "body_text": body_text,
        "video_url": video_url,
        "page_url": lesson["url"],
    }


def download_video(video_url: str, dest: pathlib.Path) -> bool:
    """Download via yt-dlp, which understands Wistia/Vimeo/YouTube embeds."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["yt-dlp", "-o", str(dest), video_url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  video download failed: {result.stderr[-500:]}")
        return False
    return True


def save_lesson(lesson_data: dict):
    module_dir = DOWNLOAD_DIR / slugify(lesson_data["module"])
    lesson_dir = module_dir / slugify(lesson_data["title"])
    lesson_dir.mkdir(parents=True, exist_ok=True)

    prompts_path = lesson_dir / "prompts.md"
    prompts_path.write_text(
        f"# {lesson_data['title']}\n\nSource: {lesson_data['page_url']}\n\n"
        f"{lesson_data['body_text']}\n"
    )

    if lesson_data["video_url"]:
        video_path = lesson_dir / "video.mp4"
        download_video(lesson_data["video_url"], video_path)
    else:
        print(f"  no video found for: {lesson_data['title']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--list-only", action="store_true",
        help="Just list lesson titles/URLs found, don't download or upload anything.",
    )
    parser.add_argument(
        "--skip-upload", action="store_true",
        help="Download locally but don't push to Drive.",
    )
    args = parser.parse_args()

    DOWNLOAD_DIR.mkdir(exist_ok=True)
    PROFILE_DIR.mkdir(exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR), headless=HEADLESS
        )
        page = context.new_page()
        wait_for_login(page)

        lessons = list_lessons(page)
        print(f"Found {len(lessons)} lessons.")
        if args.list_only:
            for lesson in lessons:
                print(f"  [{lesson['module']}] {lesson['title']} -> {lesson['url']}")
            return

        for lesson in lessons:
            print(f"Processing: {lesson['title']}")
            lesson_data = extract_lesson(page, lesson)
            save_lesson(lesson_data)

        context.close()

    if not args.skip_upload:
        service = drive_upload.get_drive_service()
        drive_upload.sync_tree(service, DOWNLOAD_DIR, DRIVE_ROOT_FOLDER_ID)


if __name__ == "__main__":
    main()
