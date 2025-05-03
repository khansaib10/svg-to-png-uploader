import os
import io
import requests
import cairosvg
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Google Drive Folder ID (optional, can be None)
DRIVE_FOLDER_ID = None  # Replace with your folder ID if needed

# Authenticate Google Drive using service account
def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        'service_account.json',
        scopes=['https://www.googleapis.com/auth/drive']
    )
    return build('drive', 'v3', credentials=creds)

# Scrape SVG download links
def get_svg_links(max_count=50):
    print("Scraping popular SVGs...")
    svg_urls = []
    page = 1
    while len(svg_urls) < max_count:
        url = f"https://www.svgrepo.com/vectors/popular/?page={page}"
        print(f"Fetching: {url}")
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.select("a.download")
        if not links:
            break
        for link in links:
            href = link.get("href")
            if href and "/download/" in href:
                full_url = f"https://www.svgrepo.com{href}"
                svg_urls.append(full_url)
            if len(svg_urls) >= max_count:
                break
        page += 1
    print(f"Total SVGs found: {len(svg_urls)}")
    return svg_urls

# Convert SVG content to PNG bytes
def convert_svg_to_png(svg_content):
    return cairosvg.svg2png(bytestring=svg_content, output_width=1200, output_height=1600)

# Upload PNG to Google Drive
def upload_to_drive(service, png_data, filename):
    file_metadata = {'name': filename}
    if DRIVE_FOLDER_ID:
        file_metadata['parents'] = [DRIVE_FOLDER_ID]

    media = MediaIoBaseUpload(io.BytesIO(png_data), mimetype='image/png')
    service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# Main process
def main():
    print("Starting script...")
    print("Authenticating Google Drive...")
    drive_service = authenticate_drive()

    svg_urls = get_svg_links(max_count=50)
    for idx, url in enumerate(svg_urls, 1):
        print(f"[{idx}] Downloading and converting: {url}")
        try:
            svg_url = url.replace("/download", "")
            r = requests.get(svg_url)
            if r.status_code != 200 or b"<svg" not in r.content:
                raise Exception("Invalid SVG data")
            png_data = convert_svg_to_png(r.content)
            filename = f"svg_image_{idx}.png"
            upload_to_drive(drive_service, png_data, filename)
        except Exception as e:
            print(f"Error converting {url}: {e}")

if __name__ == "__main__":
    main()
