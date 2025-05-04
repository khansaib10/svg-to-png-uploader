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
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded {file_path}")

# Check if image is portrait and high-quality
def is_valid_image(image_data, min_size_kb=20):
    try:
        img = Image.open(BytesIO(image_data))
        width, height = img.size
        size_kb = len(image_data) / 1024
        print(f"Checking image: {size_kb:.2f} KB, {width}x{height}")
        return size_kb >= min_size_kb and width > 500 and height > 500 and height > width
    except Exception as e:
        print(f"Image validation error: {e}")
        return False

# Scrape Pinterest: top-page images + main pin images
def scrape_full_resolution_images(query, limit=100):
    print(f"Scraping Pinterest for query: {query}")
    search_url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=opts)
    driver.get(search_url)
    time.sleep(5)

    seen = set()
    results = []

    # 1. Top-page high-quality images via srcset
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    for img in soup.find_all('img', srcset=True):
        parts = [p.strip().split(' ')[0] for p in img['srcset'].split(',')]
        try:
            best = max(parts, key=lambda u: int(u.split('/')[-1].split('x')[0]))
        except:
            best = parts[-1]
        if 'i.pinimg.com' in best and best not in seen:
            seen.add(best)
            results.append(best)
            print(f"🔝 Top search image: {best}")
        if len(results) >= limit:
            break

    # 2. Collect pin links by infinite scroll
    pin_links = set()
    last_h = driver.execute_script("return document.body.scrollHeight")
    while len(pin_links) < limit * 2:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for a in soup.find_all('a', href=True):
            h = a['href']
            if '/pin/' in h:
                pin_links.add('https://www.pinterest.com' + h.split('?')[0])
        nh = driver.execute_script("return document.body.scrollHeight")
        if nh == last_h:
            break
        last_h = nh

    print(f"Found {len(pin_links)} pin links.")

    # 3. Visit pins for main og:image
    for link in list(pin_links)[:limit]:
        if len(results) >= limit:
            break
        try:
            driver.get(link)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'img')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            meta = soup.find('meta', property='og:image')
            if meta:
                src = meta.get('content')
                if src and src not in seen:
                    seen.add(src)
                    results.append(src)
                    print(f"✅ Pin image: {src}")
        except Exception as e:
            print(f"Error loading pin {link}: {e}")

    driver.quit()
    print(f"Collected {len(results)} high-quality images.")
    return results[:limit]

# Download existing duplicates file from Google Drive
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
        print("✅ downloaded_urls.txt retrieved from Drive")
        return fid
    print("🆕 No previous duplicate file found")
    return None

# Upload updated duplicates file to Google Drive
def upload_duplicates_file(service, folder_id, file_id=None):
    meta = {'name': 'downloaded_urls.txt', 'parents': [folder_id]}
    media = MediaFileUpload('downloaded_urls.txt', mimetype='text/plain')
    if file_id:
        service.files().update(fileId=file_id, media_body=media).execute()
        print("🔁 Updated duplicates file on Drive")
    else:
        service.files().create(body=meta, media_body=media, fields='id').execute()
        print("📤 Uploaded new duplicates file to Drive")

# Main function
def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["nature"]
    download_limit = 100

    creds_b64 = os.getenv("SERVICE_ACCOUNT_BASE64")
    creds = service_account.Credentials.from_service_account_info(decode_credentials(creds_b64))
    drive = build('drive', 'v3', credentials=creds)

    dup_id = download_duplicates_file(drive, folder_id)
    downloaded = load_downloaded_urls()

    os.makedirs("temp_images", exist_ok=True)

    for q in queries:
        urls = scrape_full_resolution_images(q, download_limit)
        for i, u in enumerate(urls, 1):
            if u in downloaded:
                print(f"⏩ Skipping duplicate: {u}")
                continue
            print(f"⬇️ Downloading {i}/{len(urls)}: {u}")
            try:
                data = requests.get(u, timeout=10).content
                if not is_valid_image(data):
                    print(f"⚠️ Skipping invalid: {u}")
                    continue
                path = f"temp_images/{q.replace(' ', '_')}_{i}.jpg"
                with open(path, 'wb') as f:
                    f.write(data)
                upload_to_drive(path, folder_id, drive)
                downloaded.add(u)
                os.remove(path)
            except Exception as e:
                print(f"Error: {e}")

    save_downloaded_urls(downloaded)
    upload_duplicates_file(drive, folder_id, dup_id)

if __name__ == '__main__':
    main()
