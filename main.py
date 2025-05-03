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
UNDRAW_JSON_URL       = 'https://raw.githubusercontent.com/cuuupid/undraw-illustrations/master/undraw.json'
NUM_IMAGES            = 10   # how many illustrations to pull
# ——————————

def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=creds)

def fetch_undraw_catalog():
    print("Fetching unDraw catalog…")
    r = requests.get(UNDRAW_JSON_URL, timeout=15)
    r.raise_for_status()
    return r.json()  # list of { \"filename\": ..., \"svg\": ... }

def download_svg(svg_url):
    r = requests.get(svg_url, timeout=15)
    if r.status_code == 200 and r.content.strip().startswith(b'<svg'):
        return r.content
    print(f" ⚠️ Failed to download or invalid SVG: {svg_url}")
    return None

def convert_to_png(svg_bytes):
    return cairosvg.svg2png(bytestring=svg_bytes,
                            output_width=1200,
                            output_height=1600)

def upload_png(data_bytes, filename, drive):
    print(f"Uploading {filename}…")
    media = MediaIoBaseUpload(io.BytesIO(data_bytes), mimetype='image/png')
    meta  = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    drive.files().create(body=meta, media_body=media, fields='id').execute()
    print(f" ✔️ {filename} uploaded")

def main():
    # prepare
    os.makedirs('temp', exist_ok=True)
    drive = authenticate_drive()

    # get catalog & pick images
    catalog = fetch_undraw_catalog()
    random.shuffle(catalog)   # randomize for variety
    selection = catalog[:NUM_IMAGES]

    for entry in selection:
        name   = entry['filename'] + '.png'
        svg_url= entry['svg']
        print(f"\nProcessing illustration: {entry['filename']}")
        svg = download_svg(svg_url)
        if not svg:
            continue
        png = convert_to_png(svg)
        upload_png(png, name, drive)

    print("\nAll done!")

if __name__ == '__main__':
    main()
