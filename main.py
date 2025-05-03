import os
import io
import base64
import json
import requests
import time
from PIL import Image
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ========== GOOGLE DRIVE SETUP ==========

def load_credentials():
    service_account_base64 = os.getenv("SERVICE_ACCOUNT_BASE64")
    key_json = base64.b64decode(service_account_base64).decode("utf-8")
    credentials = service_account.Credentials.from_service_account_info(
        json.loads(key_json),
        scopes=["https://www.googleapis.com/auth/drive"]
    )
    return credentials

def upload_to_drive(service, folder_id, file_bytes, filename):
    file_metadata = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="image/jpeg")
    service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    print(f"✅ Uploaded: {filename}")

def get_drive_file_list(service, folder_id):
    results = service.files().list(q=f"'{folder_id}' in parents", fields="files(name)").execute()
    return {file["name"] for file in results.get("files", [])}

# ========== IMAGE FILTERING ==========

def is_high_quality_image(url):
    try:
        response = requests.get(url, timeout=10)
        image = Image.open(io.BytesIO(response.content))
        width, height = image.size
        ratio = height / width
        return ratio > 1.2 and height >= 1000 and width >= 500
    except:
        return False

# ========== PINTEREST SCRAPER ==========

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

    for link in list(pin_links)[:limit]:
        if len(image_urls) >= limit:
            break
        try:
            driver.get(link)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, 'img')))
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # Main image from og:image meta
            meta_img = soup.find('meta', property='og:image')
            if meta_img and meta_img.get('content'):
                image_urls.append(meta_img['content'])

            # Related images
            related_imgs = [img['src'] for img in soup.find_all('img', src=True) if "i.pinimg.com" in img['src']]
            for src in related_imgs:
                if src not in image_urls:
                    image_urls.append(src)

        except Exception as e:
            print(f"❌ Error processing pin {link}: {e}")

    driver.quit()
    print(f"✅ Total collected: {len(image_urls)}")
    return image_urls[:limit]

# ========== DOWNLOAD TRACKING ==========

def load_downloaded_urls(file_path="downloaded_urls.txt"):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return set(f.read().splitlines())
    return set()

def save_downloaded_urls(urls, file_path="downloaded_urls.txt"):
    with open(file_path, "w") as f:
        f.write("\n".join(urls))

# ========== MAIN LOGIC ==========

def main():
    query = "cars"
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    limit = 100

    print("Authenticating with Google Drive...")
    creds = load_credentials()
    drive_service = build("drive", "v3", credentials=creds)

    existing_files = get_drive_file_list(drive_service, folder_id)
    downloaded_urls = load_downloaded_urls()
    new_downloaded = set()

    print("Scraping Pinterest images...")
    urls = scrape_full_resolution_images(query, limit=limit)

    count = 1
    for url in urls:
        if url in downloaded_urls:
            print(f"⏩ Skipping duplicate: {url}")
            continue
        if not is_high_quality_image(url):
            print(f"⚠️ Skipping low-quality image: {url}")
            continue

        try:
            response = requests.get(url, timeout=10)
            image = Image.open(io.BytesIO(response.content)).convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=95)
            filename = f"{query}_{count}.jpg"
            if filename not in existing_files:
                upload_to_drive(drive_service, folder_id, buf.getvalue(), filename)
                print(f"✅ Uploaded: {filename}")
                count += 1
                new_downloaded.add(url)
            else:
                print(f"⏩ Image already exists on Google Drive: {filename}")
        except Exception as e:
            print(f"❌ Failed to upload {url}: {e}")

    downloaded_urls.update(new_downloaded)
    save_downloaded_urls(downloaded_urls)

if __name__ == "__main__":
    main()
