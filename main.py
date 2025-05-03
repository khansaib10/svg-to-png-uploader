import os
import requests
from bs4 import BeautifulSoup
from cairosvg import svg2png
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import time

# Configuration
FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'  # Google Drive folder ID
SERVICE_ACCOUNT_FILE = 'service_account.json'
BASE_URL = 'https://www.svgrepo.com/vectors/popular/'


def authenticate_drive():
    print("Authenticating Google Drive...")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds)
    return service


def get_svg_page_links(pages=3):
    print("Scraping popular SVGRepo pages...")
    svg_links = []
    for i in range(1, pages + 1):
        print(f" → loading {BASE_URL}{i}/")
        res = requests.get(f"{BASE_URL}{i}/", timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        anchors = soup.select("a[href^='/svg/']")
        for a in anchors:
            href = a.get("href")
            if href and href.count("/") >= 3:
                parts = href.strip("/").split("/")
                if len(parts) == 3:
                    svg_links.append(href)
        time.sleep(1)
    print(f"Found {len(svg_links)} SVG entries.")
    return svg_links


def extract_id_and_name(svg_page_url):
    parts = svg_page_url.strip("/").split("/")
    if len(parts) == 3 and parts[0] == "svg":
        return parts[1], parts[2]
    return None, None


def download_svg(id_, name):
    url = f"https://www.svgrepo.com/download/{id_}/{name}.svg"
    res = requests.get(url)
    if res.status_code == 200:
        return res.content
    return None


def convert_svg_to_png(svg_bytes, png_path):
    svg2png(
        bytestring=svg_bytes,
        write_to=png_path,
        output_width=1200,
        output_height=1600,
        background_color=None
    )


def upload_to_drive(service, file_path, filename):
    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID],
        "mimeType": "image/png"
    }
    media = MediaFileUpload(file_path, mimetype="image/png")
    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    print(f"Uploaded to Drive: {filename} (ID: {uploaded.get('id')})")


def main():
    print("Starting script...")
    drive_service = authenticate_drive()
    svg_pages = get_svg_page_links(pages=3)

    os.makedirs("temp", exist_ok=True)
    count = 0

    for link in svg_pages:
        id_, name = extract_id_and_name(link)
        if not id_ or not name:
            continue

        print(f"Processing: {id_}/{name}")
        svg_data = download_svg(id_, name)
        if not svg_data:
            print(" ⚠️ Could not fetch SVG.")
            continue

        svg_path = f"temp/{name}.svg"
        png_path = f"temp/{name}.png"

        try:
            with open(svg_path, "wb") as f:
                f.write(svg_data)

            convert_svg_to_png(svg_data, png_path)
            upload_to_drive(drive_service, png_path, f"{name}.png")

            print(f" ✅ Uploaded: {name}.png")

        except Exception as e:
            print(f" ❌ Failed: {e}")

        finally:
            if os.path.exists(svg_path):
                os.remove(svg_path)
            if os.path.exists(png_path):
                os.remove(png_path)

        count += 1
        if count >= 10:
            break

    print("All done.")

if __name__ == "__main__":
    main()
