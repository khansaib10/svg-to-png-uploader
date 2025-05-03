import os
import io
import time
import requests
import cairosvg
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
DRIVE_FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'
KEYWORDS = ['bike', 'cat', 'flower', 'mountain', 'tree']
MAX_PER_KEY = 5       # how many SVGs per keyword
PAGE_DELAY = 1        # seconds between API requests

# Authenticate Google Drive
def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=creds)

# Fetch SVG links from OpenClipart JSON API for a keyword
def get_openclipart_links(keyword, max_count=MAX_PER_KEY):
    print(f"Searching OpenClipart for keyword: '{keyword}'")
    links = []
    page = 1
    while len(links) < max_count:
        api_url = (
            'https://openclipart.org/search/json/'
            f'?query={keyword}&amount={max_count}&page={page}'
        )
        print(f" → GET {api_url}")
        try:
            resp = requests.get(api_url, timeout=10)
            resp.raise_for_status()
            data = resp.json().get('payload', [])
        except Exception as e:
            print(f" ⚠️ API request failed: {e}")
            break

        if not data:
            break

        for item in data:
            svg_obj = item.get('svg', {})
            raw_url = svg_obj.get('svg')
            if raw_url and raw_url not in links:
                links.append(raw_url)
                if len(links) >= max_count:
                    break
        page += 1
        time.sleep(PAGE_DELAY)
    print(f" • Found {len(links)} SVGs for '{keyword}'")
    return links

# Download, convert, and upload

def process_svg(svg_url, prefix, drive):
    print(f"Downloading SVG: {svg_url}")
    r = requests.get(svg_url, timeout=15)
    if r.status_code != 200 or not r.content.strip().startswith(b'<svg'):
        print(" ⚠️ Invalid SVG, skipping")
        return False

    png_data = cairosvg.svg2png(
        bytestring=r.content,
        output_width=1200,
        output_height=1600
    )

    name = svg_url.split('/')[-1].replace('.svg', '')
    filename = f"{prefix}_{name}.png"
    print(f"Uploading {filename}...")
    media = MediaIoBaseUpload(io.BytesIO(png_data), mimetype='image/png')
    meta  = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    drive.files().create(body=meta, media_body=media, fields='id').execute()
    print(f" ✔️ Uploaded {filename}")
    return True

# Main workflow
def main():
    print("Starting script...")
    drive = authenticate_drive()

    for kw in KEYWORDS:
        links = get_openclipart_links(kw)
        for svg_url in links:
            process_svg(svg_url, kw, drive)

    print("All done.")

if __name__ == '__main__':
    main()
