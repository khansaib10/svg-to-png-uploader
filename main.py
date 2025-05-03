import os
import io
import time
import requests
from bs4 import BeautifulSoup
from cairosvg import svg2png
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ====== CONFIG ======
BATCH_SIZE = 50  # Change as needed
START_INDEX = 0  # For batching
PNG_WIDTH, PNG_HEIGHT = 1200, 1600
GOOGLE_DRIVE_FOLDER_ID = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
# ====================

print("Starting script...")

# Authenticate Google Drive
def get_drive_service():
    print("Authenticating Google Drive...")
    creds = service_account.Credentials.from_service_account_file("service_account.json", scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)

# Upload PNG to Drive
def upload_to_drive(service, file_name, file_data):
    file_metadata = {
        "name": file_name,
        "parents": [GOOGLE_DRIVE_FOLDER_ID]
    }
    media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype="image/png")
    uploaded_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    print(f"Uploaded: {file_name} (ID: {uploaded_file.get('id')})")

# Scrape popular SVG links
def scrape_svgrepo_popular_links(limit=5000):
    print("Scraping popular SVGs...")
    base_url = "https://www.svgrepo.com/vectors/popular/"
    links = []
    page = 1
    while len(links) < limit:
        url = f"{base_url}?page={page}"
        print(f"Fetching: {url}")
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to load page {page}. Status code: {response.status_code}")
            break
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("a[href^='/svg/']")
        if not cards:
            print("No more SVGs found.")
            break
        for card in cards:
            href = card.get("href", "")
            if "/svg/" in href:
                download_url = f"https://www.svgrepo.com{href}/download"
                if download_url not in links:
                    links.append(download_url)
                if len(links) >= limit:
                    break
        page += 1
    print(f"Total SVGs found: {len(links)}")
    return links


# Convert SVG to PNG bytes
def convert_svg_to_png(svg_url):
    try:
        response = requests.get(svg_url)
        if response.status_code != 200:
            print(f"Failed to download SVG: {svg_url}")
            return None
        png_bytes = svg2png(bytestring=response.content, output_width=PNG_WIDTH, output_height=PNG_HEIGHT)
        return png_bytes
    except Exception as e:
        print(f"Error converting {svg_url}: {e}")
        return None

# Main process
def main():
    print(f"Starting batch: {START_INDEX} to {START_INDEX + BATCH_SIZE}")
    drive_service = get_drive_service()
    svg_links = scrape_svgrepo_popular_links(limit=START_INDEX + BATCH_SIZE)
    for i, svg_url in enumerate(svg_links[START_INDEX:START_INDEX + BATCH_SIZE]):
        print(f"[{i+1}] Downloading and converting: {svg_url}")
        png_data = convert_svg_to_png(svg_url)
        if png_data:
            file_name = f"svgrepo_{START_INDEX + i + 1}.png"
            upload_to_drive(drive_service, file_name, png_data)
        time.sleep(1)  # to be gentle to the server

if __name__ == "__main__":
    main()
