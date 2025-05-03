import os
import io
import time
import ssl
import urllib3
import requests
import cairosvg
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Suppress only the single InsecureRequestWarning from urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'  # Google Drive folder ID
SERVICE_ACCOUNT_FILE = 'service_account.json'
KEYWORDS = ['bike', 'cat', 'flower', 'mountain', 'tree']
MAX_PER_KEY = 5       # how many SVGs per keyword
PAGE_DELAY = 1        # seconds between API requests

# Custom HTTPS adapter to disable SSL verification
def create_ssl_bypass_session():
    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, connections, maxsize, block=False):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=ctx)

    session = requests.Session()
    session.mount('https://', SSLAdapter())
    return session

# Authenticate Google Drive using service account
def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=creds)

# Fetch SVG links from OpenClipart JSON API with SSL bypass
def get_openclipart_links(keyword, max_count=MAX_PER_KEY, session=None):
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
            resp = session.get(api_url, timeout=10, verify=False)
            resp.raise_for_status()
            data = resp.json().get('payload', [])
        except Exception as e:
            print(f" ⚠️ API request failed: {e}")
            break

        if not data:
            break

        for item in data:
            svg_url = item.get('svg', {}).get('svg')
            if svg_url and svg_url not in links:
                links.append(svg_url)
                if len(links) >= max_count:
                    break
        page += 1
        time.sleep(PAGE_DELAY)
    print(f" • Found {len(links)} SVGs for '{keyword}'")
    return links

# Process each SVG: download, convert, upload
def process_svg(svg_url, prefix, drive, session=None):
    print(f"Downloading SVG: {svg_url}")
    try:
        r = session.get(svg_url, timeout=15, verify=False)
    except Exception as e:
        print(f" ⚠️ Download error: {e}")
        return False
    if r.status_code != 200 or not r.content.strip().startswith(b'<svg'):
        print(" ⚠️ Invalid SVG content, skipping")
        return False

    # Convert SVG to PNG bytes
    try:
        png_data = cairosvg.svg2png(
            bytestring=r.content,
            output_width=1200,
            output_height=1600
        )
    except Exception as e:
        print(f" ⚠️ Conversion error: {e}")
        return False

    # Upload PNG to Drive
    name = svg_url.split('/')[-1].replace('.svg', '')
    filename = f"{prefix}_{name}.png"
    print(f"Uploading {filename}...")
    media = MediaIoBaseUpload(io.BytesIO(png_data), mimetype='image/png')
    meta = {'name': filename, 'parents': [FOLDER_ID]}
    try:
        drive.files().create(body=meta, media_body=media, fields='id').execute()
        print(f" ✔️ {filename} uploaded")
    except Exception as e:
        print(f" ⚠️ Upload error: {e}")
        return False
    return True

# Main workflow
if __name__ == '__main__':
    print("Starting script...")
    drive = authenticate_drive()
    session = create_ssl_bypass_session()

    for kw in KEYWORDS:
        links = get_openclipart_links(kw, session=session)
        for url in links:
            process_svg(url, kw, drive, session=session)

    print("All done.")
