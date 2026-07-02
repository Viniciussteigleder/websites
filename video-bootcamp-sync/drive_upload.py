"""Idempotent Google Drive uploader.

Mirrors a local directory tree into a Drive folder, reusing folders/files
that already exist (matched by name + parent) so re-running the sync only
uploads what's new.

Auth: OAuth "Desktop app" client. Put the downloaded client secret at
./credentials.json (gitignored). First run opens a browser to authorize;
the resulting token is cached at ./token.json.
"""

from __future__ import annotations

import pathlib

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDENTIALS_FILE = pathlib.Path(__file__).parent / "credentials.json"
TOKEN_FILE = pathlib.Path(__file__).parent / "token.json"


def get_drive_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def find_child(service, parent_id: str, name: str, is_folder: bool) -> str | None:
    mime_clause = (
        "mimeType = 'application/vnd.google-apps.folder'"
        if is_folder
        else "mimeType != 'application/vnd.google-apps.folder'"
    )
    query = (
        f"'{parent_id}' in parents and name = '{name}' "
        f"and {mime_clause} and trashed = false"
    )
    results = (
        service.files()
        .list(q=query, fields="files(id, name)", pageSize=1)
        .execute()
    )
    files = results.get("files", [])
    return files[0]["id"] if files else None


def get_or_create_folder(service, parent_id: str, name: str) -> str:
    existing = find_child(service, parent_id, name, is_folder=True)
    if existing:
        return existing
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_file(service, parent_id: str, local_path: pathlib.Path, mime_type: str):
    """Upload local_path into parent_id, skipping if a same-named file exists."""
    existing = find_child(service, parent_id, local_path.name, is_folder=False)
    if existing:
        print(f"  skip (exists): {local_path.name}")
        return existing
    media = MediaFileUpload(str(local_path), mimetype=mime_type, resumable=True)
    metadata = {"name": local_path.name, "parents": [parent_id]}
    uploaded = service.files().create(body=metadata, media_body=media, fields="id").execute()
    print(f"  uploaded: {local_path.name}")
    return uploaded["id"]


def sync_tree(service, local_root: pathlib.Path, drive_root_id: str):
    """Mirror local_root/<Module>/<Lesson>/{video.*, prompts.md} into Drive."""
    for module_dir in sorted(p for p in local_root.iterdir() if p.is_dir()):
        module_id = get_or_create_folder(service, drive_root_id, module_dir.name)
        for lesson_dir in sorted(p for p in module_dir.iterdir() if p.is_dir()):
            lesson_id = get_or_create_folder(service, module_id, lesson_dir.name)
            print(f"{module_dir.name}/{lesson_dir.name}")
            for f in sorted(lesson_dir.iterdir()):
                if f.suffix == ".md":
                    upload_file(service, lesson_id, f, "text/markdown")
                elif f.suffix in (".mp4", ".mov", ".webm"):
                    upload_file(service, lesson_id, f, f"video/{f.suffix.lstrip('.')}")
