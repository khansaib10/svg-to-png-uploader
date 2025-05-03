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

# Scrape Pinterest: improved top-page image extraction and pin-page images
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
    image_urls = []
    seen = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    # 1. Extract high-quality images from search results via srcset
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    for img in soup.find_all('img', srcset=True):
        srcset = img['srcset']
        # parse all resolutions
        candidates = [part.strip().split(' ')[0] for part in srcset.split(',')]
        # choose highest width value
        try:
            best = max(candidates, key=lambda u: int(u.split('/')[-1].split('x')[0]))
        except:
            best = candidates[-1]
        if 'i.pinimg.com' in best and best not in seen:
            seen.add(best)
            image_urls.append(best)
            print(f"🔝 Top search image: {best}")
        if len(image_urls) >= limit:
            break

    # 2. Infinite scroll to collect pin URLs
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

    # 3. Visit each pin page to extract og:image and any additional high-res images
    for link in list(pin_links)[:limit * 2]:
        if len(image_urls) >= limit:
            break
        try:
            driver.get(link)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'img'))
            )
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            meta = soup.find('meta', property='og:image')
            if meta:
                src = meta.get('content')
                if src and src not in seen:
                    seen.add(src)
                    image_urls.append(src)
                    print(f"✅ Main pin image: {src}")
        except Exception as e:
            print(f"❌ Error loading pin {link}: {e}")

    driver.quit()
    print(f"Collected {len(image_urls)} high-quality images.")
    return image_urls[:limit]

# Download existing duplicates file from Google Drive
def download_duplicates_file(service, folder_id):
    results = service.files().list(
        q=f"'{folder_id}' in parents and name='downloaded_urls.txt' and trashed=false",
