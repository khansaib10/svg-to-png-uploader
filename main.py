import os
import time
import base64
import json
import requests
from io import BytesIO
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# — Helpers ——————————————————————————————————————————————————————————

def decode_credentials(b64: str):
    return json.loads(base64.b64decode(b64))

def load_downloaded_urls(path="downloaded_urls.txt"):
    return set(open(path).read().splitlines()) if os.path.exists(path) else set()

def save_downloaded_urls(urls, path="downloaded_urls.txt"):
    with open(path, "w") as f:
        f.write("\n".join(urls))

def upload_to_drive(local_path, folder_id, drive_service):
    meta = {'name': os.path.basename(local_path), 'parents': [folder_id]}
    media = MediaFileUpload(local_path, mimetype='image/jpeg')
    drive_service.files().create(body=meta, media_body=media, fields='id').execute()

def download_duplicates_file(drive_service, folder_id):
    q = f"'{folder_id}' in parents and name='downloaded_urls.txt' and trashed=false"
    res = drive_service.files().list(q=q, fields='files(id)').execute().get('files',[])
    if not res: return None
    fid = res[0]['id']
    req = drive_service.files().get_media(fileId=fid)
    with open("downloaded_urls.txt","wb") as f:
        dl = MediaIoBaseDownload(f, req)
        done = False
        while not done:
            _, done = dl.next_chunk()
    return fid

def upload_duplicates_file(drive_service, folder_id, file_id):
    media = MediaFileUpload("downloaded_urls.txt", mimetype='text/plain')
    meta = {'name':'downloaded_urls.txt','parents':[folder_id]}
    if file_id:
        drive_service.files().update(fileId=file_id, media_body=media).execute()
    else:
        drive_service.files().create(body=meta, media_body=media, fields='id').execute()

def is_portrait(image_data: bytes):
    try:
        w,h = Image.open(BytesIO(image_data)).size
        return h > w
    except:
        return False

# — Scraper ——————————————————————————————————————————————————————————

def scrape_top_pins(query: str, limit: int = 50):
    url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=opts)
    driver.get(url)

    # Wait for the feed of pins to appear
    WebDriverWait(driver, 15).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[role='feed'] a[href*='/pin/']"))
    )
    time.sleep(2)  # allow a moment for all top pins to load

    # Collect first `limit` unique pin URLs from the feed container
    anchors = driver.find_elements(By.CSS_SELECTOR, "div[role='feed'] a[href*='/pin/']")
    pin_links = []
    for a in anchors:
        href = a.get_attribute("href").split('?')[0]
        if href not in pin_links:
            pin_links.append(href)
        if len(pin_links) >= limit:
            break

    print(f"🖼 Found {len(pin_links)} top pins for '{query}'")
    results, seen = [], set()

    # Visit each pin and fetch its full-res image via og:image
    for link in pin_links:
        if len(results) >= limit:
            break
        try:
            driver.get(link)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'head')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            meta = soup.find('meta', property='og:image')
            src = meta.get('content') if meta else None
            if src and src not in seen:
                seen.add(src)
                results.append(src)
                print("✅", src)
        except Exception as e:
            print("⚠️ Error on", link, ":", e)

    driver.quit()
    return results[:limit]

# — Main ——————————————————————————————————————————————————————————

def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["cars"]
    limit = 50

    creds = service_account.Credentials.from_service_account_info(
        decode_credentials(os.getenv("SERVICE_ACCOUNT_BASE64"))
    )
    drive = build('drive','v3',credentials=creds)

    dup_id = download_duplicates_file(drive, folder_id)
    downloaded = load_downloaded_urls()
    os.makedirs("temp_images", exist_ok=True)

    for q in queries:
        urls = scrape_top_pins(q, limit)
        for idx, url in enumerate(urls, 1):
            if url in downloaded:
                print("⏩ Duplicate", url)
                continue
            print("⬇️ Downloading", url)
            try:
                data = requests.get(url, timeout=10).content
                if not is_portrait(data):
                    print("⚠️ Skipped (not portrait)", url)
                    continue
                path = f"temp_images/{q.replace(' ', '_')}_{idx}.jpg"
                with open(path, 'wb') as f:
                    f.write(data)
                upload_to_drive(path, folder_id, drive)
                downloaded.add(url)
                os.remove(path)
            except Exception as e:
                print("❌ Error downloading", url, ":", e)

    save_downloaded_urls(downloaded)
    upload_duplicates_file(drive, folder_id, dup_id)

if __name__ == "__main__":
    main()
