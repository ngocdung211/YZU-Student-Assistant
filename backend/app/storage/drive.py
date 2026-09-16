"""Personal Drive OAuth and connection checks adapted from HaUI Drive helpers."""

import argparse
import io
import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import google_auth_httplib2
import httplib2
import httpx

from ..config import BACKEND_DIRECTORY, Settings, load_settings

# Approved by the user to access the existing manually selected Drive folder.
SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveSetupError(Exception):
    """Carry a fixed, non-secret setup status for the readiness report."""


def token_path(settings: Settings) -> Path:
    """Resolve token storage relative to the backend directory."""
    path = Path(settings.values.get("GOOGLE_DRIVE_TOKEN_FILE") or "credentials/token.json")
    return path if path.is_absolute() else BACKEND_DIRECTORY / path


def save_token(path: Path, credentials: Credentials) -> None:
    """Store OAuth tokens locally with owner-only file permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as token_file:
        os.fchmod(token_file.fileno(), 0o600)
        token_file.write(credentials.to_json())


def authorize(settings: Settings) -> None:
    """Run explicit local browser consent, never during API startup."""
    path = Path(settings.require("GOOGLE_DRIVE_CREDENTIALS_JSON"))
    if not path.is_absolute():
        path = BACKEND_DIRECTORY / path
    config = json.loads(path.read_text())
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    credentials = flow.run_local_server(
    host="127.0.0.1",
    port=0,
    timeout_seconds=180,
    authorization_prompt_message="Complete Google consent in your browser.",
    success_message="Drive authorization completed. You may close this tab.",
    )
    save_token(token_path(settings), credentials)


def create_service(settings: Settings):
    """Load or refresh user tokens without opening an interactive login."""
    path = token_path(settings)
    if not path.exists():
        raise DriveSetupError("oauth_authorization_required")
    credentials = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not credentials.valid:
        if not credentials.refresh_token:
            raise DriveSetupError("oauth_authorization_required")
        credentials.refresh(Request())
        save_token(path, credentials)
    transport = google_auth_httplib2.AuthorizedHttp(
        credentials, http=httplib2.Http(timeout=20))
    return build("drive", "v3", http=transport, cache_discovery=False)


def check_folder(service, folder_id: str) -> None:
    """Check the configured destination exists and allows file creation."""
    folder = service.files().get(
        fileId=folder_id, supportsAllDrives=True,
        fields="mimeType,trashed,capabilities(canAddChildren)",
    ).execute()
    if folder.get("trashed") or folder.get("mimeType") != "application/vnd.google-apps.folder":
        raise DriveSetupError("invalid_drive_folder")
    if not folder.get("capabilities", {}).get("canAddChildren"):
        raise DriveSetupError("drive_folder_not_writable")


def check_public_reference(service, folder_id: str) -> None:
    """Create, share, anonymously read, and delete a dedicated test file."""
    content = b"YZU Student Assistant public reference connection check."
    result = service.files().create(
        body={"name": "yzu-connection-check.txt", "parents": [folder_id]},
        media_body=MediaIoBaseUpload(io.BytesIO(content), mimetype="text/plain"),
        fields="id,webViewLink", supportsAllDrives=True,
    ).execute()
    file_id = result["id"]
    try:
        service.permissions().create(
            fileId=file_id, body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
        # This request has no OAuth credentials: verify a student can read it.
        response = httpx.get("https://drive.google.com/uc",
                             params={"export": "download", "id": file_id},
                             follow_redirects=True, timeout=20)
        if response.status_code != 200 or response.content != content or not result.get("webViewLink"):
            raise DriveSetupError("public_reference_check_failed")
    finally:
        # Only delete the probe created above; never touch existing documents.
        service.files().delete(fileId=file_id, supportsAllDrives=True).execute()


def main() -> None:
    """Provide explicit one-time authorization and public-reference checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorize", action="store_true")
    parser.add_argument("--check-public", action="store_true")
    arguments = parser.parse_args()
    settings = load_settings()
    service = None
    try:
        if arguments.authorize:
            authorize(settings)
        service = create_service(settings)
        folder_id = settings.require("GOOGLE_DRIVE_FOLDER_ID")
        check_folder(service, folder_id)
        if arguments.check_public:
            check_public_reference(service, folder_id)
        print("Drive public reference verified." if arguments.check_public else "Drive folder connection verified.")
    except Exception as error:
        # OAuth exception strings can contain authorization codes or tokens.
        status = str(error) if isinstance(error, DriveSetupError) else type(error).__name__
        print(f"Drive check failed: {status}. Check local OAuth setup.")
        raise SystemExit(1) from None
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    main()


def upload_pdf(service, path: Path, filename: str, folder_id: str,
               document_id: str) -> str:
    """Upload an original PDF and return its Drive ID for subsequent cleanup."""
    result = service.files().create(
        body={"name": filename, "parents": [folder_id],
              "appProperties": {"yzu_document_id": document_id}},
        media_body=MediaFileUpload(str(path), mimetype="application/pdf", resumable=True),
        fields="id", supportsAllDrives=True,
    ).execute()
    return result["id"]


def publish_pdf(service, file_id: str) -> str:
    """Require public-reader permission before returning the original-file link."""
    service.permissions().create(
        fileId=file_id, body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True,
    ).execute()
    result = service.files().get(
        fileId=file_id, fields="webViewLink", supportsAllDrives=True).execute()
    if not result.get("webViewLink"):
        raise DriveSetupError("drive_reference_link_missing")
    return result["webViewLink"]


def delete_import_pdf(service, file_id: str) -> None:
    """Remove only the original uploaded by a failed import."""
    service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
