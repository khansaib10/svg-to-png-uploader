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

# Decode base64 service account credentials
def decode_credentials(base64_credentials):
    print("🔐 Decoding credentials...")
    decoded = base64.b64decode(base64_credentials)
    return json.loads(decoded)

# Load downloaded URLs from file
def load_downloaded_urls(path="downloaded_urls.txt"):
    if os.path.exists(path):
        with open(path, "r") as f:
            return set(f.read().splitlines())
    return set()

# Save downloaded URLs to file
def save_downloaded_urls(urls, path="downloaded_urls.txt"):
    with open(path, "w") as f:
        f.write("\n".join(urls))

# Upload a file to Google Drive
def upload_to_drive(file_path, folder_id, drive_service):
    print(f"📤 Uploading {file_path} to Drive...")
    metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    drive_service.files().create(body=metadata, media_body=media, fields='id').execute()
    print("✅ Uploaded!")

# Download the duplicates file from Drive
def download_duplicates_file(drive_service, folder_id):
    q = f"'{folder_id}' in parents and name='downloaded_urls.txt' and trashed=false"
    res = drive_service.files().list(q=q, fields='files(id)').execute().get('files', [])
    if not res:
        print("🆕 No duplicates file on Drive.")
        return None
    fid = res[0]['id']
    req = drive_service.files().get_media(fileId=fid)
    with open("downloaded_urls.txt", "wb") as f:
        downloader = MediaIoBaseDownload(f, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    print("⬇️ downloaded_urls.txt retrieved.")
    return fid

# Upload the updated duplicates file to Drive
def upload_duplicates_file(drive_service, folder_id, file_id=None):
    media = MediaFileUpload("downloaded_urls.txt", mimetype='text/plain')
    metadata = {'name': 'downloaded_urls.txt', 'parents': [folder_id]}
    if file_id:
        drive_service.files().update(fileId=file_id, media_body=media).execute()
        print("🔁 Updated duplicates file on Drive.")
    else:
        drive_service.files().create(body=metadata, media_body=media, fields='id').execute()
        print("📤 Uploaded new duplicates file.")

# Check if an image is portrait
def is_portrait(image_data):
    try:
        img = Image.open(BytesIO(image_data))
        w, h = img.size
        return h > w
    except:
        return False

# Scrape the first `limit` visible pins from the top feed
def scrape_top_pins(query, limit=50):
    print(f"🔍 Scraping Pinterest for: {query}")
    search_url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=opts)
    driver.get(search_url)

    # Wait until feed container loads at least one pin link
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='feed'] a[href*='/pin/']"))
    )
    time.sleep(2)  # ensure rest of top pins render

    # Collect first `limit` unique pin URLs from the feed
    anchors = driver.find_elements(By.CSS_SELECTOR, "div[role='feed'] a[href*='/pin/']")
    pin_links = []
    for a in anchors:
        href = a.get_attribute("href").split('?')[0]
        if href not in pin_links:
            pin_links.append(href)
        if len(pin_links) >= limit:
            break

    print(f"🖼 Found {len(pin_links)} top pins.")
    results = []
    seen = set()

    # Visit each pin to get its full-resolution og:image
    for link in pin_links:
        if len(results) >= limit:
            break
        try:
            driver.get(link)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'head')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            meta = soup.find('meta', property='og:image')
            if meta and (src := meta.get('content')) and src not in seen:
                seen.add(src)
                results.append(src)
                print("✅", src)
        except Exception as e:
            print("⚠️ Error loading pin:", link, e)

    driver.quit()
    print(f"📸 Collected {len(results)} images.")
    return results[:limit]

# Main execution
def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["cars"]  # add more queries if desired
    limit = 50

    creds = service_account.Credentials.from_service_account_info(
        decode_credentials(os.getenv("SERVICE_ACCOUNT_BASE64"))
    )
    drive = build('drive', 'v3', credentials=creds)

    # Load duplicates
    dup_id = download_duplicates_file(drive, folder_id)
    downloaded = load_downloaded_urls()
    os.makedirs("temp_images", exist_ok=True)

    for query in queries:
        urls = scrape_top_pins(query, limit)
        for idx, url in enumerate(urls, start=1):
            if url in downloaded:
                print("⏩ Skipping duplicate:", url)
                continue
            print(f"⬇️ Downloading {idx}/{len(urls)}: {url}")
            try:
                data = requests.get(url, timeout=10).content
                if not is_portrait(data):
                    print("⚠️ Skipped (not portrait):", url)
                    continue
                path = f"temp_images/{query.replace(' ', '_')}_{idx}.jpg"
                with open(path, 'wb') as f:
                    f.write(data)
                upload_to_drive(path, folder_id, drive)
                downloaded.add(url)
                os.remove(path)
            except Exception as e:
                print("❌ Error downloading:", url, e)

    save_downloaded_urls(downloaded)
    upload_duplicates_file(drive, folder_id, dup_id)

if __name__ == "__main__":
    main()
