import os
import io
import requests
import cairosvg
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import hashlib

# === CONFIGURATION ===
OUTPUT_WIDTH = 1200
OUTPUT_HEIGHT = 1600
DRIVE_FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'  # Replace this

# === BATCHING SUPPORT ===
BATCH_SIZE = int(os.getenv("BATCH_SIZE", 100))
BATCH_START = int(os.getenv("BATCH_START", 0))
NUM_FILES = BATCH_SIZE

# === SETUP GOOGLE DRIVE AUTH ===
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'service_account.json'

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

# === FUNCTION: Upload to Google Drive ===
def upload_to_drive(filename, filepath):
    file_metadata = {
        'name': filename,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(filepath, mimetype='image/png')
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    return uploaded_file.get('id')

# === FUNCTION: Scrape SVG Links from OpenClipart ===
def scrape_svg_links(limit=5000):
    base_url = 'https://openclipart.org'
    search_url = f'{base_url}/recent'
    svg_links = []
    page = 0

    while len(svg_links) < limit:
        page_url = f"{search_url}?page={page}"
        print(f"Scraping: {page_url}")
        response = requests.get(page_url)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.item a[href*="/detail/"]')

        if not items:
            break  # No more results

        for a_tag in items:
            detail_url = base_url + a_tag['href']
            detail_resp = requests.get(detail_url)
            if detail_resp.status_code != 200:
                continue
            detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
            download_link_tag = detail_soup.find('a', href=True, text='Download SVG')
            if download_link_tag:
                svg_links.append(base_url + download_link_tag['href'])
            if len(svg_links) >= limit:
                break
        page += 1

    return svg_links

# === FUNCTION: Convert SVG to PNG ===
def convert_svg_to_png(svg_content, output_path):
    cairosvg.svg2png(bytestring=svg_content, write_to=output_path,
                     output_width=OUTPUT_WIDTH, output_height=OUTPUT_HEIGHT)

# === MAIN WORKFLOW ===
def main():
    print(f"Starting batch: {BATCH_START} to {BATCH_START + BATCH_SIZE}")
    svg_links = scrape_svg_links(limit=5000)

    batch_links = svg_links[BATCH_START:BATCH_START + NUM_FILES]

    os.makedirs("output", exist_ok=True)

    for idx, svg_url in enumerate(batch_links):
        try:
            print(f"[{idx + 1}] Downloading: {svg_url}")
            svg_resp = requests.get(svg_url)
            if svg_resp.status_code != 200:
                print("Failed to download SVG.")
                continue

            # Use hash of URL as unique filename
            hash_name = hashlib.md5(svg_url.encode()).hexdigest()
            png_filename = f"{hash_name}.png"
            png_path = os.path.join("output", png_filename)

            # Skip if already processed
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
