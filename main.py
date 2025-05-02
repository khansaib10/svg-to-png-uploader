import os
import requests
import cairosvg
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configs
SVG_DIR = 'svgs'
PNG_DIR = 'pngs'
NUM_FILES = 5000
DRIVE_FOLDER_ID = 'your_google_drive_folder_id'
SCOPES = ['https://www.googleapis.com/auth/drive.file']
SERVICE_ACCOUNT_FILE = 'service_account.json'

# Set up Google Drive service
def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

# Scrape OpenClipart
def scrape_svg_links():
    print("Scraping OpenClipart...")
    svg_links = set()
    base_url = 'https://openclipart.org'
    page = 0

    while len(svg_links) < NUM_FILES:
        url = f'{base_url}/search?page={page}&query='
        res = requests.get(url)
        soup = BeautifulSoup(res.content, 'html.parser')
        for a in soup.select('a[href^="/detail/"]'):
            detail_url = base_url + a['href']
            detail_res = requests.get(detail_url)
            detail_soup = BeautifulSoup(detail_res.content, 'html.parser')
            download_link = detail_soup.find('a', text='Download SVG')
            if download_link:
                svg_links.add(base_url + download_link['href'])
        print(f"Page {page}: Found {len(svg_links)} links so far...")
        if not soup.select('a[rel="next"]'):
            break
        page += 1

    return list(svg_links)[:NUM_FILES]

# Download SVGs
def download_svgs(svg_links):
    os.makedirs(SVG_DIR, exist_ok=True)
    for i, link in enumerate(svg_links):
        filename = os.path.join(SVG_DIR, f'image_{i}.svg')
        if os.path.exists(filename):
            continue
        try:
            r = requests.get(link, timeout=10)
            if r.status_code == 200:
                with open(filename, 'wb') as f:
                    f.write(r.content)
                print(f"Downloaded: {filename}")
        except Exception as e:
            print(f"Failed to download {link}: {e}")

# Convert SVG to PNG
def convert_svgs_to_png():
    os.makedirs(PNG_DIR, exist_ok=True)
    for svg_file in os.listdir(SVG_DIR):
        svg_path = os.path.join(SVG_DIR, svg_file)
        png_path = os.path.join(PNG_DIR, svg_file.replace('.svg', '.png'))
        if os.path.exists(png_path):
            continue
        try:
            cairosvg.svg2png(
                url=svg_path,
                write_to=png_path,
                output_width=1200,
                output_height=1600,
                background_color=None
            )
            print(f"Converted: {png_path}")
        except Exception as e:
            print(f"Failed to convert {svg_file}: {e}")

# Upload PNG to Drive
def upload_pngs_to_drive(service):
    for file_name in os.listdir(PNG_DIR):
        file_path = os.path.join(PNG_DIR, file_name)
        file_metadata = {
            'name': file_name,
            'parents': [DRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(file_path, mimetype='image/png')
        try:
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print(f"Uploaded: {file_name}")
        except Exception as e:
            print(f"Failed to upload {file_name}: {e}")

# Main script
if __name__ == '__main__':
    drive_service = get_drive_service()
    links = scrape_svg_links()
    download_svgs(links)
    convert_svgs_to_png()
    upload_pngs_to_drive(drive_service)
