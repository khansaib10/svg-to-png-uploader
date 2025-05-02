import os
import io
import requests
import cairosvg
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import hashlib
import time

# === CONFIGURATION ===
OUTPUT_WIDTH = 1200
OUTPUT_HEIGHT = 1600
DRIVE_FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'  # Replace this

# === BATCHING SUPPORT ===
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
BATCH_START = int(os.getenv("BATCH_START", 0))
NUM_FILES = BATCH_SIZE

# === GOOGLE DRIVE AUTH ===
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'service_account.json'

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

def upload_to_drive(filename, filepath):
    file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaFileUpload(filepath, mimetype='image/png')
    uploaded_file = drive_service.files().create(
        body=file_metadata, media_body=media, fields='id').execute()
    return uploaded_file.get('id')

# === SCRAPE SVG LINKS FROM SVGREPO ===
def scrape_svgrepo_svg_links(limit=5000):
    base_url = 'https://www.svgrepo.com'
    svg_links = []
    page = 1

    # Add a User-Agent header to mimic a browser request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    while len(svg_links) < limit:
        print(f"Scraping SVGRepo page {page}...")
        url = f"{base_url}/svg/{page}/"
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code != 200:
                print(f"Failed to load page {page}. Status code: {response.status_code}")
                break

            soup = BeautifulSoup(response.text, 'html.parser')
            icons = soup.select("a[href^='/download/']")

            for a in icons:
                href = a.get("href")
                if href.endswith(".svg"):
                    svg_links.append(base_url + href)

            page += 1
            time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"Request failed for page {page}: {e}")
            break

    return svg_links

def convert_svg_to_png(svg_content, output_path):
    cairosvg.svg2png(bytestring=svg_content, write_to=output_path,
                     output_width=OUTPUT_WIDTH, output_height=OUTPUT_HEIGHT)

def main():
    print(f"Starting batch: {BATCH_START} to {BATCH_START + BATCH_SIZE}")
    svg_links = scrape_svgrepo_svg_links(limit=5000)
    batch_links = svg_links[BATCH_START:BATCH_START + NUM_FILES]

    os.makedirs("output", exist_ok=True)

    for idx, svg_url in enumerate(batch_links):
        try:
            print(f"[{idx + 1}] Downloading: {svg_url}")
            svg_resp = requests.get(svg_url)
            if svg_resp.status_code != 200:
                print("Failed to download SVG.")
                continue

            hash_name = hashlib.md5(svg_url.encode()).hexdigest()
            png_filename = f"{hash_name}.png"
            png_path = os.path.join("output", png_filename)

            if os.path.exists(png_path):
                print(f"Already exists: {png_filename}")
                continue

            convert_svg_to_png(svg_resp.content, png_path)
            upload_to_drive(png_filename, png_path)
            print(f"Uploaded: {png_filename}")

        except Exception as e:
            print(f"Error processing {svg_url}: {e}")

if __name__ == "__main__":
    main()
