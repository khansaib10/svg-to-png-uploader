import os
import requests
from cairosvg import svg2png
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from bs4 import BeautifulSoup

# Configuration
SERVICE_ACCOUNT_FILE = 'service_account.json'
DRIVE_FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'  # Google Drive folder ID

# Google Drive authentication
def authenticate_drive():
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES
    )
    drive_service = build('drive', 'v3', credentials=creds)
    return drive_service

# Upload PNG to Google Drive
def upload_to_drive(drive_service, file_path, file_name):
    file_metadata = {
        'name': file_name,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaFileUpload(file_path, mimetype='image/png')
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    print(f'Uploaded {file_name} to Google Drive with ID: {file["id"]}')
    os.remove(file_path)  # Clean up after upload

# Fetch SVG links based on keywords
def get_svg_links_by_keyword(keyword, max_count=10):
    base_url = f'https://www.svgrepo.com/search/{keyword}/'
    svg_links = []
    for page in range(1, 6):  # Check first 5 pages per keyword
        url = f"{base_url}?page={page}"
        print(f"Fetching: {url}")
        response = requests.get(url)
        if response.status_code != 200:
            print(f"⚠️ Failed to load page {page} for '{keyword}'")
            break
        soup = BeautifulSoup(response.content, 'html.parser')
        svg_items = soup.find_all('a', class_='vector-card__download-link')
        for item in svg_items:
            if len(svg_links) >= max_count:
                break
            href = item.get('href')
            svg_links.append(f'https://www.svgrepo.com{href}')
        if len(svg_links) >= max_count:
            break
    print(f"Found {len(svg_links)} SVG links for '{keyword}'")
    return svg_links

# Download SVG and convert to PNG
def download_and_convert_to_png(svg_url, output_path):
    response = requests.get(svg_url)
    if response.status_code == 200:
        svg_content = response.content
        svg2png(bytestring=svg_content, write_to=output_path)
    else:
        print(f"⚠️ Failed to download SVG: {svg_url}")

# Main function
def main():
    keywords = ['bike', 'cat', 'flower', 'mountain', 'tree']  # Add or modify keywords
    max_count = 10  # Max number of SVGs per keyword

    print("Authenticating Google Drive...")
    drive_service = authenticate_drive()

    for keyword in keywords:
        print(f"\nScraping SVGs for keyword: {keyword}")
        svg_links = get_svg_links_by_keyword(keyword, max_count)
        for svg_url in svg_links:
            file_name = svg_url.split('/')[-2] + '.png'
            output_path = os.path.join('/tmp', file_name)

            print(f"Processing: {svg_url}")
            try:
                download_and_convert_to_png(svg_url, output_path)
                upload_to_drive(drive_service, output_path, file_name)
            except Exception as e:
                print(f"⚠️ Failed to process {svg_url}, skipping. Error: {e}")

    print("All done!")

if __name__ == '__main__':
    main()
