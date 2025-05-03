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
    print("Decoding credentials...")
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
    print(f"Uploading {file_path} to Google Drive...")
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded {file_path} to Google Drive. File ID: {file['id']}")

# Check if image is portrait and high-quality
def is_valid_image(image_data, min_size_kb=20):
    try:
        image = Image.open(BytesIO(image_data))
        width, height = image.size
        size_kb = len(image_data) / 1024
        print(f"Checking image: {size_kb:.2f} KB, {width}x{height}")
        return size_kb >= min_size_kb and width > 500 and height > 500 and height > width
    except Exception as e:
        print(f"Image validation error: {e}")
        return False

# Scrape Pinterest and visit pin pages for full-resolution images
def scrape_full_resolution_images(query, limit=100):
    print(f"Scraping Pinterest for query: {query}")
    search_url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(search_url)
    time.sleep(5)

    pin_links = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    # Infinite scroll to gather pin URLs
    while len(pin_links) < limit * 2:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/pin/' in href:
                pin_links.add('https://www.pinterest.com' + href.split('?')[0])
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    print(f"Found {len(pin_links)} pin links.")
    image_urls = []

    # Visit each pin page to extract og:image
    for link in list(pin_links)[:limit * 2]:
        if len(image_urls) >= limit:
            break
        try:
            driver.get(link)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'head'))
            )
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            meta = soup.find('meta', property='og:image')
            if meta and meta.get('content'):
                src = meta['content']
                if src not in image_urls:
                    image_urls.append(src)
                    print(f"✅ Found image: {src}")
        except Exception as e:
            print(f"❌ Error loading pin {link}: {e}")

    driver.quit()
    print(f"Collected {len(image_urls)} full-resolution images.")
    return image_urls[:limit]

# Download existing duplicates file from Google Drive
def download_duplicates_file(service, folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents and name='downloaded_urls.txt' and trashed=false",
        fields='files(id,name)'
    ).execute()
    items = results.get('files', [])

    if items:
        file_id = items[0]['id']
        request = service.files().get_media(fileId=file_id)
        with open('downloaded_urls.txt', 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        print("✅ downloaded_urls.txt retrieved from Drive")
        return file_id
    else:
        print("🆕 No previous duplicate file found")
        return None

# Upload updated duplicates file to Google Drive
def upload_duplicates_file(service, folder_id, file_id=None):
    file_metadata = {'name': 'downloaded_urls.txt', 'parents': [folder_id]}
    media = MediaFileUpload('downloaded_urls.txt', mimetype='text/plain')
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        print("🔁 Updated duplicates file on Drive")
    else:
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print("📤 Uploaded new duplicates file to Drive")

# Main function
def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["ai girl"]
    download_limit = 100

    credentials_json = os.getenv("SERVICE_ACCOUNT_BASE64")
    credentials_dict = decode_credentials(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict)
    drive_service = build('drive', 'v3', credentials=credentials)

    # Load duplicates
    dup_file_id = download_duplicates_file(drive_service, folder_id)
    downloaded_urls = load_downloaded_urls()

    os.makedirs("temp_images", exist_ok=True)

    for query in queries:
        image_urls = scrape_full_resolution_images(query, download_limit)
        for idx, url in enumerate(image_urls):
            if url in downloaded_urls:
                print(f"⏩ Skipping duplicate: {url}")
                continue
            print(f"⬇️ Downloading {idx+1}/{len(image_urls)}: {url}")
            try:
                img_data = requests.get(url, timeout=10).content
                if not is_valid_image(img_data):
                    print(f"⚠️ Skipping invalid: {url}")
                    continue
                img_path = f"temp_images/{query.replace(' ', '_')}_{idx+1}.jpg"
                with open(img_path, 'wb') as f:
                    f.write(img_data)
                upload_to_drive(img_path, folder_id, drive_service)
                downloaded_urls.add(url)
                os.remove(img_path)
            except Exception as e:
                print(f"❌ Error: {e}")

    save_downloaded_urls(downloaded_urls)
    upload_duplicates_file(drive_service, folder_id, dup_file_id)

if __name__ == '__main__':
    main()
