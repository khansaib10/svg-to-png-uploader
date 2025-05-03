import os
import io
import time
import requests
import cairosvg
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# -------------- CONFIGURATION --------------
MAX_SVG = 10                 # how many SVGs to process
PAGE_DELAY = 3               # seconds to wait per page load
DRIVE_FOLDER_ID = None       # or set your Drive folder ID string
# -------------------------------------------

def authenticate_drive():
    print("Authenticating Google Drive...")
    creds = service_account.Credentials.from_service_account_file(
        'service_account.json',
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=creds)

def get_svg_links(max_count=MAX_SVG):
    print("Scraping popular SVG pages...")
    chrome_opts = Options()
    chrome_opts.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_opts)

    links = []
    page = 1
    while len(links) < max_count:
        url = f"https://www.svgrepo.com/vectors/popular/{page}/"
        print(f" → loading {url}")
        driver.get(url)
        time.sleep(PAGE_DELAY)

        cards = driver.find_elements(By.CSS_SELECTOR, 'a[href^="/svg/"]')
        if not cards:
            break
        for c in cards:
            href = c.get_attribute("href")
            # pattern: https://www.svgrepo.com/svg/12345/name
            if href and '/svg/' in href:
                dl = href.rstrip('/') + '/download'  # no trailing slash
                if dl not in links:
                    links.append(dl)
                if len(links) >= max_count:
                    break
        page += 1

    driver.quit()
    print(f"Found {len(links)} download links.")
    return links

def download_convert_upload(link, drive_service):
    print(f"Processing: {link}")
    # fetch raw SVG from download endpoint
    r = requests.get(link, timeout=30)
    if r.status_code != 200 or not r.content.strip().startswith(b'<svg'):
        print(" ⚠️ Failed to fetch raw SVG, skipping.")
        return
    svg_data = r.content

    # convert in-memory
    png = cairosvg.svg2png(bytestring=svg_data, output_width=1200, output_height=1600)

    # prepare upload
    filename = os.path.basename(link).replace('/download','') + '.png'
    metadata = {'name': filename}
    if DRIVE_FOLDER_ID:
        metadata['parents'] = [DRIVE_FOLDER_ID]
    media = MediaIoBaseUpload(io.BytesIO(png), mimetype='image/png')

    # upload
    drive_service.files().create(body=metadata, media_body=media, fields='id').execute()
    print(f" ✔️ Uploaded {filename}")

def main():
    drive = authenticate_drive()
    links = get_svg_links()
    for link in links:
        download_convert_upload(link, drive)
    print("All done.")

if __name__ == "__main__":
    main()
