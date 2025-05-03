import os
import io
import time
import requests
import cairosvg
from bs4 import BeautifulSoup
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ----------------- CONFIGURATION -----------------
MAX_SVG = 10        # Number of SVGs to process
PAGE_DELAY = 3      # Seconds to wait for page load
DRIVE_FOLDER_ID = None  # Set to your Drive folder ID if needed
# --------------------------------------------------

def authenticate_drive():
    print("Authenticating Google Drive...")
    creds = service_account.Credentials.from_service_account_file(
        'service_account.json',
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=creds)

def get_svg_links(max_count=MAX_SVG):
    print("Scraping popular SVGs...")
    svg_urls = []
    page = 1

    # Set up headless Chrome
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    while len(svg_urls) < max_count:
        url = f"https://www.svgrepo.com/vectors/popular/{page}/"
        print(f"Fetching: {url}")
        driver.get(url)
        time.sleep(PAGE_DELAY)

        cards = driver.find_elements(By.CSS_SELECTOR, 'a[href^="/svg/"]')
        if not cards:
            print("No more SVG cards found.")
            break

        for card in cards:
            href = card.get_attribute("href")
            # Example href: https://www.svgrepo.com/svg/12345/name
            if href and href.startswith("https://www.svgrepo.com/svg/"):
                download_url = f"{href}/download/"
                if download_url not in svg_urls:
                    svg_urls.append(download_url)
                if len(svg_urls) >= max_count:
                    break

        page += 1

    driver.quit()
    print(f"Total SVGs found: {len(svg_urls)}")
    return svg_urls

def download_and_convert(svg_url, drive_service):
    print(f"Processing: {svg_url}")
    # Fetch the raw SVG page URL (without /download/)
    svg_page_url = svg_url.replace("/download/", "")
    resp = requests.get(svg_page_url)
    if resp.status_code != 200 or b"<svg" not in resp.content:
        print(f"Failed to fetch SVG page: {svg_page_url}")
        return

    # Extract the direct .svg file link from the page
    soup = BeautifulSoup(resp.text, 'html.parser')
    link = soup.find('a', string='SVG')
    if not link or not link['href'].endswith('.svg'):
        print("SVG download link not found on page.")
        return
    raw_svg_url = link['href']
    if raw_svg_url.startswith('/'):
        raw_svg_url = f"https://www.svgrepo.com{raw_svg_url}"

    # Download the raw SVG
    svg_data = requests.get(raw_svg_url).content

    # Convert to PNG in-memory
    png_data = cairosvg.svg2png(bytestring=svg_data, output_width=1200, output_height=1600)

    # Upload to Drive
    filename = os.path.basename(raw_svg_url).replace('.svg', '.png')
    file_metadata = {'name': filename}
    if DRIVE_FOLDER_ID:
        file_metadata['parents'] = [DRIVE_FOLDER_ID]
    media = MediaIoBaseUpload(io.BytesIO(png_data), mimetype='image/png')
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded {filename} to Drive")

def main():
    drive_service = authenticate_drive()
    links = get_svg_links()
    for url in links:
        download_and_convert(url, drive_service)
    print("All done!")

if __name__ == "__main__":
    main()
