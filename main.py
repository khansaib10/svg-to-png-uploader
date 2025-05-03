import os
import io
import random
import requests
import cairosvg
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ——— CONFIG ———
SERVICE_ACCOUNT_FILE = 'service_account.json'
DRIVE_FOLDER_ID       = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'
NUM_IMAGES            = 10    # total illustrations to grab
# ——————————

def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=creds)

def fetch_undraw_catalog():
    page = 1
    all_items = []
    print("Fetching unDraw catalog via API…")
    while True:
        url = f"https://undraw.co/api/illustrations?page={page}"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        for item in data['illos']:
            # each item has 'title' (string) and 'image' (SVG URL)
            all_items.append({
                'title': item['title'],
                'svg_url': item['image']
            })
        if not data.get('hasMore'):
            break
        page = data.get('nextPage')
    print(f"• Catalog size: {len(all_items)} illustrations")
    return all_items

def download_and_convert(svg_url):
    resp = requests.get(svg_url, timeout=15)
    if resp.status_code != 200 or not resp.content.strip().startswith(b'<svg'):
        print(f" ⚠️ Bad SVG at {svg_url}, skipping")
        return None
    return cairosvg.svg2png(
        bytestring=resp.content,
        output_width=1200,
        output_height=1600
    )

def upload_png(data, name, drive):
    print(f"Uploading {name}…")
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype='image/png')
    meta  = {'name': name, 'parents': [DRIVE_FOLDER_ID]}
    drive.files().create(body=meta, media_body=media, fields='id').execute()
    print(f" ✔️ {name} uploaded")

def main():
    os.makedirs('temp', exist_ok=True)
    drive = authenticate_drive()

    catalog = fetch_undraw_catalog()
    random.shuffle(catalog)
    selection = catalog[:NUM_IMAGES]

    for entry in selection:
        fname = entry['title'].lower().replace(' ', '_') + '.png'
        print(f"\nProcessing illustration: {entry['title']}")
        png_data = download_and_convert(entry['svg_url'])
        if not png_data:
            continue
        upload_png(png_data, fname, drive)

    print("\nAll done.")

if __name__ == '__main__':
    main()
