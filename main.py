import os
import time
import base64
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from PIL import Image
from io import BytesIO

# Decode base64 service account credentials
def decode_credentials(base64_credentials):
    print("🔐 Decoding credentials...")
    decoded_bytes = base64.b64decode(base64_credentials)
    return json.loads(decoded_bytes)

# Load downloaded URLs from file
def load_downloaded_urls():
    if os.path.exists("downloaded_urls.txt"):
        with open("downloaded_urls.txt", "r") as f:
            return set(f.read().splitlines())
    return set()

# Save downloaded URLs to file
def save_downloaded_urls(urls):
    with open("downloaded_urls.txt", "w") as f:
        f.write("\n".join(urls))

# Upload image to Google Drive
def upload_to_drive(file_path, folder_id, drive_service):
    print(f"📤 Uploading {file_path}...")
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"✅ Upload complete.")

# Check if image is portrait and high-quality
def is_valid_image(image_data, min_size_kb=20):
    try:
        img = Image.open(BytesIO(image_data))
        width, height = img.size
        size_kb = len(image_data) / 1024
        print(f"📏 Checking: {width}x{height}, {size_kb:.1f} KB")
        return size_kb >= min_size_kb and height > width and width > 400 and height > 600
    except Exception as e:
        print(f"❌ Image validation error: {e}")
        return False

# Scrape high-quality Pinterest images
def scrape_top_pins_and_images(query, limit=50):
    print(f"🔍 Scraping for: {query}")
    url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(url)
    time.sleep(4)  # Let content load

    # Grab top pins without scrolling
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    pin_links = []
    for a in soup.find_all('a', href=True):
        h = a['href']
        if '/pin/' in h:
            full = 'https://www.pinterest.com' + h.split('?')[0]
            if full not in pin_links:
                pin_links.append(full)
        if len(pin_links) >= limit:
            break

    print(f"🖼 Found {len(pin_links)} top pins.")

    seen = set()
    results = []

    for pin_url in pin_links:
        try:
            driver.get(pin_url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'img')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Main pin image
            meta = soup.find('meta', property='og:image')
            if meta:
                src = meta.get('content')
                if src and src not in seen:
                    seen.add(src)
                    results.append(src)
                    print(f"✅ Pin image: {src}")

            # High-quality related images (only 736x)
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src and '/736x/' in src and src not in seen:
                    seen.add(src)
                    results.append(src)
                    print(f"🔗 Related image: {src}")

            if len(results) >= limit:
                break

        except Exception as e:
            print(f"❌ Error opening {pin_url}: {e}")

    driver.quit()
    print(f"📸 Total images collected: {len(results)}")
    return results[:limit]

# Download duplicates file from Google Drive
def download_duplicates_file(service, folder_id):
    res = service.files().list(
        q=f"'{folder_id}' in parents and name='downloaded_urls.txt' and trashed=false",
        fields='files(id,name)'
    ).execute()
    items = res.get('files', [])
    if items:
        fid = items[0]['id']
        req = service.files().get_media(fileId=fid)
        with open('downloaded_urls.txt', 'wb') as f:
            dl = MediaIoBaseDownload(f, req)
            done = False
            while not done:
                status, done = dl.next_chunk()
        print("⬇️ duplicates file downloaded from Drive.")
        return fid
    return None

# Upload duplicates file to Google Drive
def upload_duplicates_file(service, folder_id, file_id=None):
    meta = {'name': 'downloaded_urls.txt', 'parents': [folder_id]}
    media = MediaFileUpload('downloaded_urls.txt', mimetype='text/plain')
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        service.files().create(body=meta, media_body=media, fields='id').execute()
    print("🔁 Updated duplicates file.")

# Main function
def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["cars"]  # Change keywords here
    download_limit = 50

    creds_b64 = os.getenv("SERVICE_ACCOUNT_BASE64")
    creds = service_account.Credentials.from_service_account_info(decode_credentials(creds_b64))
    drive = build('drive', 'v3', credentials=creds)

    dup_id = download_duplicates_file(drive, folder_id)
    downloaded = load_downloaded_urls()

    os.makedirs("temp_images", exist_ok=True)

    for query in queries:
        urls = scrape_top_pins_and_images(query, download_limit)
        for i, u in enumerate(urls, 1):
            if u in downloaded:
                print(f"⏩ Skipping duplicate: {u}")
                continue
            print(f"⬇️ Downloading {i}/{len(urls)}: {u}")
            try:
                img_data = requests.get(u, timeout=10).content
                if not is_valid_image(img_data):
                    print(f"⚠️ Invalid image: {u}")
                    continue
                path = f"temp_images/{query.replace(' ', '_')}_{i}.jpg"
                with open(path, 'wb') as f:
                    f.write(img_data)
                upload_to_drive(path, folder_id, drive)
                downloaded.add(u)
                os.remove(path)
            except Exception as e:
                print(f"❌ Error downloading: {e}")

    save_downloaded_urls(downloaded)
    upload_duplicates_file(drive, folder_id, dup_id)

if __name__ == '__main__':
    main()
