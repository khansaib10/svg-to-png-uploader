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

def decode_credentials(base64_credentials):
    print("🔐 Decoding credentials...")
    return json.loads(base64.b64decode(base64_credentials))

def load_downloaded_urls():
    return set(open("downloaded_urls.txt").read().splitlines()) if os.path.exists("downloaded_urls.txt") else set()

def save_downloaded_urls(urls):
    with open("downloaded_urls.txt", "w") as f:
        f.write("\n".join(urls))

def upload_to_drive(file_path, folder_id, service):
    print(f"📤 Uploading {file_path}...")
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    service.files().create(body=file_metadata, media_body=media).execute()
    print("✅ Upload complete.")

def is_valid_image(image_data, min_size_kb=20):
    try:
        img = Image.open(BytesIO(image_data))
        width, height = img.size
        size_kb = len(image_data) / 1024
        return size_kb >= min_size_kb and width > 500 and height > 500 and height > width
    except:
        return False

def scrape_images(query, limit=100):
    print(f"🔍 Scraping for: {query}")
    search_url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=opts)
    driver.get(search_url)
    time.sleep(4)  # Wait to load top page

    # Get top pin links without scrolling
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    top_pins = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if '/pin/' in href:
            pin_url = 'https://www.pinterest.com' + href.split('?')[0]
            top_pins.add(pin_url)
        if len(top_pins) >= limit:
            break

    print(f"🖼 Found {len(top_pins)} top pins.")
    collected = []
    seen = set()

    for link in list(top_pins)[:limit]:
        if len(collected) >= limit:
            break
        try:
            driver.get(link)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'img')))
            page = BeautifulSoup(driver.page_source, 'html.parser')

            # Main pin image
            meta = page.find('meta', property='og:image')
            if meta:
                main_src = meta.get('content')
                if main_src and main_src not in seen:
                    collected.append(main_src)
                    seen.add(main_src)
                    print(f"✅ Pin image: {main_src}")

            # Related images with /736x/
            for img in page.find_all('img'):
                src = img.get('src') or ''
                if '/736x/' in src and src not in seen:
                    collected.append(src)
                    seen.add(src)
                    print(f"🔗 Related image: {src}")
                    if len(collected) >= limit:
                        break
        except Exception as e:
            print(f"⚠️ Error on {link}: {e}")

    driver.quit()
    print(f"📸 Total images collected: {len(collected)}")
    return collected[:limit]

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
    print("📁 No duplicates file found on Drive.")
    return None

def upload_duplicates_file(service, folder_id, file_id=None):
    media = MediaFileUpload('downloaded_urls.txt', mimetype='text/plain')
    metadata = {'name': 'downloaded_urls.txt', 'parents': [folder_id]}
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        print("🔁 Updated duplicates file.")
    else:
        service.files().create(body=metadata, media_body=media, fields='id').execute()
        print("📤 Uploaded new duplicates file.")

def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["cars"]
    limit = 100

    creds_json = decode_credentials(os.getenv("SERVICE_ACCOUNT_BASE64"))
    creds = service_account.Credentials.from_service_account_info(creds_json)
    drive = build('drive', 'v3', credentials=creds)

    file_id = download_duplicates_file(drive, folder_id)
    downloaded = load_downloaded_urls()
    os.makedirs("temp_images", exist_ok=True)

    for query in queries:
        urls = scrape_images(query, limit)
        for i, url in enumerate(urls):
            if url in downloaded:
                print(f"⏩ Skipping duplicate: {url}")
                continue
            try:
                img_data = requests.get(url, timeout=10).content
                if not is_valid_image(img_data):
                    print(f"❌ Invalid image: {url}")
                    continue
                filename = f"temp_images/{query.replace(' ', '_')}_{i+1}.jpg"
                with open(filename, 'wb') as f:
                    f.write(img_data)
                upload_to_drive(filename, folder_id, drive)
                downloaded.add(url)
                os.remove(filename)
            except Exception as e:
                print(f"⚠️ Error downloading {url}: {e}")

    save_downloaded_urls(downloaded)
    upload_duplicates_file(drive, folder_id, file_id)

if __name__ == "__main__":
    main()
