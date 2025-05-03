import os
import requests
from bs4 import BeautifulSoup
from cairosvg import svg2png
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import time

# === CONFIGURATION ===
FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'  # <-- Your actual Google Drive folder ID
SERVICE_ACCOUNT_FILE = 'service_account.json'
KEYWORDS = ['bike', 'cat', 'tree', 'flower', 'mountain']

# === AUTHENTICATE GOOGLE DRIVE ===
def authenticate_drive():
    print("Authenticating Google Drive...")
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds)

# === SCRAPE SVG URLs BASED ON KEYWORDS ===
def get_svg_links_by_keywords(keywords, pages=2):
    all_links = []
    base = "https://www.svgrepo.com"
    for kw in keywords:
        print(f"Searching SVGRepo for: '{kw}'")
        for p in range(1, pages+1):
            url = f"{base}/search/{kw}/?page={p}"
            print(f" → loading {url}")
            try:
                res = requests.get(url, timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                anchors = soup.select("a[href^='/svg/']")
                for a in anchors:
                    href = a.get("href")
                    if href and href.count("/") >= 3:
                        parts = href.strip("/").split("/")
                        if len(parts) == 3 and parts[0] == "svg":
                            all_links.append(parts[1:])  # [id, name]
            except Exception as e:
                print(f" ⚠️ Failed to load page {p} for '{kw}': {e}")
            time.sleep(1)
    return all_links

# === DOWNLOAD SVG FROM SVGREPO ===
def download_svg(id_, name):
    url = f"https://www.svgrepo.com/download/{id_}/{name}.svg"
    res = requests.get(url)
    if res.status_code == 200:
        return res.content
    return None

# === CONVERT SVG TO PNG ===
def convert_svg_to_png(svg_bytes, png_path):
    svg2png(bytestring=svg_bytes, write_to=png_path, output_width=1200, output_height=1600, background_color=None)

# === UPLOAD TO GOOGLE DRIVE ===
def upload_to_drive(service, file_path, filename):
    file_metadata = {
        "name": filename,
        "parents": [FOLDER_ID],
        "mimeType": "image/png"
    }
    media = MediaFileUpload(file_path, mimetype="image/png")
    uploaded = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    return uploaded.get("id")

# === MAIN FUNCTION ===
def main():
    print("Starting script...")
    drive_service = authenticate_drive()
    os.makedirs("temp", exist_ok=True)

    svg_entries = get_svg_links_by_keywords(KEYWORDS, pages=2)
    print(f"Found {len(svg_entries)} SVG entries.")

    count = 0
    for id_, name in svg_entries:
        print(f"Processing: {id_}/{name}")
        try:
            svg_data = download_svg(id_, name)
            if not svg_data:
                print(" ⚠️ Could not fetch SVG.")
                continue

            svg_path = f"temp/{name}.svg"
            png_path = f"temp/{name}.png"

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
        if count >= 15:
            break

    print("All done.")

if __name__ == "__main__":
    main()
