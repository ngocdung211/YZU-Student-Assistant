from getpass import getpass
import json
import tempfile
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


REGULATIONS_URL = (
    "https://www.yzu.edu.tw/admin/aa/index.php/en-us/regulations"
)

API_URL = "http://127.0.0.1:8000"
PROGRESS_FILE = Path("regulation_upload_progress.json")


def login(username: str, password: str) -> requests.Session:
    """Login once and return an authenticated session."""

    session = requests.Session()

    response = session.post(
        f"{API_URL}/auth/token",
        json={
            "username": username,
            "password": password,
        },
        headers={
            "x-csrf-protection": "1",
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    # Adjust this if your /auth/token response uses another field.
    token = data.get("access_token") or data.get("token")

    if token:
        session.headers.update({
            "Authorization": f"Bearer {token}"
        })

    session.headers.update({
        "x-csrf-protection": "1",
    })

    return session


def get_pdf_links() -> list[dict]:
    """Extract regulation titles and PDF URLs from the YZU page."""

    response = requests.get(REGULATIONS_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    documents = []

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if ".pdf" not in href.lower():
            continue

        documents.append({
            "title": link.get_text(" ", strip=True),
            "url": urljoin(REGULATIONS_URL, href),
        })

    return documents


def load_progress() -> dict:
    if not PROGRESS_FILE.exists():
        return {}

    return json.loads(
        PROGRESS_FILE.read_text(encoding="utf-8")
    )


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.write_text(
        json.dumps(progress, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def upload_regulations(
    session: requests.Session,
    max_files: int | None = None,
) -> None:
    """
    Download and upload regulations.

    Already completed URLs are skipped automatically.
    max_files allows the job to be processed in small batches.
    """

    documents = get_pdf_links()
    progress = load_progress()

    print(f"Found {len(documents)} PDF files.")

    completed = sum(
        1
        for item in progress.values()
        if item.get("status") == "completed"
    )

    print(f"Already completed: {completed}")
    print(f"Remaining: {len(documents) - completed}")
    print()

    uploaded_this_run = 0

    for index, document in enumerate(documents, start=1):

        url = document["url"]
        title = document["title"]

        # Resume support
        if progress.get(url, {}).get("status") == "completed":
            print(f"[{index}/{len(documents)}] SKIP: {title}")
            continue

        if max_files is not None and uploaded_this_run >= max_files:
            print()
            print(f"Batch limit reached: {max_files}")
            print("Run the script again to continue.")
            break

        print(f"[{index}/{len(documents)}] Processing: {title}")

        try:
            # ---------------------------------------------------------
            # 1. Download PDF
            # ---------------------------------------------------------

            pdf_response = requests.get(
                url,
                timeout=60,
            )
            pdf_response.raise_for_status()

            if not pdf_response.content.startswith(b"%PDF-"):
                raise ValueError("Downloaded file is not a PDF.")

            filename = (
                Path(url.split("?")[0]).name
                or f"regulation-{index}.pdf"
            )

            # ---------------------------------------------------------
            # 2. Upload to your backend
            # ---------------------------------------------------------

            with tempfile.NamedTemporaryFile(
                suffix=".pdf",
            ) as temp:

                temp.write(pdf_response.content)
                temp.flush()

                with open(temp.name, "rb") as pdf:
                    response = session.post(
                        f"{API_URL}/admin/documents",
                        files={
                            "file": (
                                filename,
                                pdf,
                                "application/pdf",
                            )
                        },
                        timeout=300,
                    )

            if response.status_code != 201:
                raise RuntimeError(
                    f"Upload failed "
                    f"({response.status_code}): "
                    f"{response.text}"
                )

            result = response.json()

            # ---------------------------------------------------------
            # 3. Immediately save progress
            # ---------------------------------------------------------

            progress[url] = {
                "status": "completed",
                "title": title,
                "document_id": result.get("document_id"),
                "filename": filename,
            }

            save_progress(progress)

            uploaded_this_run += 1

            print(
                f"    ✓ Uploaded "
                f"document_id={result.get('document_id')}"
            )

        except KeyboardInterrupt:
            print("\nStopped by user.")
            print("Progress has already been saved.")
            break

        except Exception as error:
            progress[url] = {
                "status": "failed",
                "title": title,
                "error": str(error),
            }

            save_progress(progress)

            print(f"    ✗ FAILED: {error}")

    print()
    print("Done.")

if __name__ == "__main__":
    session = login(
        username=input("Administrator username: ").strip(),
        password=getpass("Administrator password: "),
    )

    upload_regulations(
        session
    )
