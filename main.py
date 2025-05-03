import os
import requests
from bs4 import BeautifulSoup
import cairosvg
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Define your keywords
KEYWORDS = ['bike', 'cat', 'tree', 'flower', 'mountain']
MAX_FILES = 15
GOOGLE_DRIVE_FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'

# Authenticate Google Drive
def authenticate_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

# Search and download SVGs
def download_svgs():
    svg_files = []
    for keyword in KEYWORDS:
        response = requests.get(f'https://publicdomainvectors.org/en/search/{keyword}/')
        soup = BeautifulSoup(response.text, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links:
            if link['href'].endswith('.svg'):
                svg_url = link['href']
                svg_name = svg_url.split('/')[-1]
                svg_path = os.path.join('svgs', svg_name)
                os.makedirs('svgs', exist_ok=True)
                with open(svg_path, 'wb') as f:
                    f.write(requests.get(svg_url).content)
                svg_files.append(svg_path)
                if len(svg_files) >= MAX_FILES:
                    return svg_files
    return svg_files

# Convert SVG to PNG
def convert_svgs_to_pngs(svg_files):
    png_files = []
    os.makedirs('pngs', exist_ok=True)
    for svg_file in svg_files:
        png_file = os.path.join('pngs', os.path.splitext(os.path.basename(svg_file))[0] + '.png')
        cairosvg.svg2png(url=svg_file, write_to=png_file)
        png_files.append(png_file)
    return png_files

# Upload PNGs to Google Drive
def upload_to_drive(service, png_files):
    for png_file in png_files:
        file_metadata = {
            'name': os.path.basename(png_file),
            'parents': [GOOGLE_DRIVE_FOLDER_ID]
        }
        media = MediaFileUpload(png_file, mimetype='image/png')
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()

def main():
    service = authenticate_drive()
    svg_files = download_svgs()
    png_files = convert_svgs_to_pngs(svg_files)
    upload_to_drive(service, png_files)

if __name__ == '__main__':
    main()
