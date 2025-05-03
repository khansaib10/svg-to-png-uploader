import os
import time
import base64
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image
from io import BytesIO

DUPLICATES_FILE = "downloaded_urls.txt"

def decode_credentials(base64_credentials):
    decoded_bytes = base64.b64decode(base64_credentials)
    return json.loads(decoded_bytes)

def upload_to_drive(file_path, folder_id, credentials_json):
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    credentials_dict = decode_credentials(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded: {os.path.basename(file_path)}")

def is_valid_image(image_data, min_size_kb=40):
    try:
        image = Image.open(BytesIO(image_data))
        width, height = image.size
        size_kb = len(image_data) / 1024
        aspect_ratio = height / width if width else 0
        return (
            size_kb >= min_size_kb and
            width > 500 and height > 500 and
            1.7 <= aspect_ratio <= 1.85
        )
    except:
        return False

def extract_real_image_url(driver, pin_url):
    try:
        driver.get(pin_url)
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            return og_image["content"]
    except:
        pass
    return None

def get_pin_page_urls(query, driver, limit=50):
    driver.get(f"https://www.pinterest.com/search/pins/?q={query}")
    time.sleep(5)
    pin_urls = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    while len(pin_urls) < limit:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if href.startswith("/pin/") and href.count("/") == 3:
                full_url = f"https://www.pinterest.com{href}"
                pin_urls.add(full_url)
                if len(pin_urls) >= limit:
                    break
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    return list(pin_urls)

def load_downloaded_urls():
    if os.path.exists(DUPLICATES_FILE):
        with open(DUPLICATES_FILE, 'r') as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_downloaded_url(url):
    with open(DUPLICATES_FILE, 'a') as f:
        f.write(url + "\n")

def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["bike", "bike lovers", "Harley Davidson bike", "motorbike", "heavy bikes"]
    base64_credentials = os.getenv("SERVICE_ACCOUNT_BASE64")
    download_limit_per_query = 30
    downloaded_urls = load_downloaded_urls()

    os.makedirs("temp_images", exist_ok=True)
    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Chrome(options=options)

    for query in queries:
        print(f"\n🔍 Searching: {query}")
        pin_page_urls = get_pin_page_urls(query, driver, limit=download_limit_per_query)

        for idx, pin_url in enumerate(pin_page_urls):
            if pin_url in downloaded_urls:
                print(f"⏭️  Skipping duplicate pin: {pin_url}")
                continue

            real_img_url = extract_real_image_url(driver, pin_url)
            if not real_img_url or real_img_url in downloaded_urls:
                print(f"⏭️  Skipping duplicate or invalid image URL.")
                continue

            try:
                img_data = requests.get(real_img_url).content
                if not is_valid_image(img_data):
                    print(f"❌ Skipping low-quality image.")
                    continue

                filename = f"temp_images/{query.replace(' ', '_')}_{idx+1}.jpg"
                with open(filename, 'wb') as f:
                    f.write(img_data)

                upload_to_drive(filename, folder_id, base64_credentials)
                os.remove(filename)
                downloaded_urls.add(real_img_url)
                save_downloaded_url(real_img_url)
            except Exception as e:
                print(f"⚠️ Error processing image: {e}")

    driver.quit()
    print("\n✅ Script completed.")

if __name__ == "__main__":
    main()
