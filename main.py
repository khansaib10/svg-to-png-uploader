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
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Decode base64 service account
def decode_credentials(base64_credentials):
    print("🔐 Decoding credentials...")
    decoded_bytes = base64.b64decode(base64_credentials)
    return json.loads(decoded_bytes)

# Setup Google Drive API
def setup_drive_service(base64_credentials):
    SCOPES = ['https://www.googleapis.com/auth/drive']
    credentials_dict = decode_credentials(base64_credentials)
    credentials = service_account.Credentials.from_service_account_info(credentials_dict, scopes=SCOPES)
    return build('drive', 'v3', credentials=credentials)

# Download a file from Google Drive
def download_drive_file(service, file_name):
    print(f"⬇️  Checking for {file_name} in Drive...")
    results = service.files().list(q=f"name='{file_name}'", fields="files(id, name)").execute()
    items = results.get('files', [])
    if not items:
        print("🆕 No previous download record found.")
        return set(), None

    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    downloaded = BytesIO()
    downloader = requests.get(request.uri, headers={'Authorization': 'Bearer ' + service._http.credentials.token})
    downloaded.write(downloader.content)
    downloaded.seek(0)
    lines = downloaded.read().decode().splitlines()
    return set(lines), file_id

# Upload or update file in Drive
def upload_or_update_file(service, content, file_name, folder_id, existing_id=None):
    file_metadata = {'name': file_name, 'parents': [folder_id]}
    media = MediaFileUpload(content, mimetype='text/plain') if isinstance(content, str) else content

    if existing_id:
        print(f"🔁 Updating existing {file_name} on Drive...")
        service.files().update(fileId=existing_id, media_body=media).execute()
    else:
        print(f"📤 Uploading {file_name} to Drive...")
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# Scrape Pinterest pin links
def scrape_pinterest_links(query, limit=50):
    print(f"🔍 Searching Pinterest for: {query}")
    search_url = f"https://www.pinterest.com/search/pins/?q={query}"
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(search_url)
    time.sleep(5)

    pin_links = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    while len(pin_links) < limit:
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/pin/') and href.count('/') == 3:
                pin_links.add("https://www.pinterest.com" + href)

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    driver.quit()
    return list(pin_links)[:limit]

# Extract full-res image from pin page
def get_image_from_pin(pin_url):
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=options)
    driver.get(pin_url)

    try:
        # Wait for images to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "img"))
        )
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        img_tags = soup.find_all("img")

        # Prioritize high-res sources
        for img in img_tags:
            src = img.get("src", "")
            if "i.pinimg.com/originals" in src or "i.pinimg.com/736x" in src:
                driver.quit()
                return src

    except Exception as e:
        print(f"⚠️ Error extracting image from {pin_url}: {e}")

    driver.quit()
    return None


# Validate image by size and aspect ratio
def is_valid_image(image_data):
    image = Image.open(BytesIO(image_data))
    width, height = image.size
    aspect_ratio = height / width
    size_kb = len(image_data) / 1024
    print(f"📐 Size: {width}x{height}, Ratio: {aspect_ratio:.2f}, KB: {size_kb:.2f}")
    return 0.55 < aspect_ratio < 0.65 and size_kb >= 20 and width > 500 and height > 500

# Upload image
def upload_image_to_drive(service, file_path, folder_id):
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"✅ Uploaded: {file_path} -> ID: {file['id']}")

# Main logic
def main():
    query = "ai girl"
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    base64_credentials = os.getenv("SERVICE_ACCOUNT_BASE64")

    service = setup_drive_service(base64_credentials)
    downloaded_urls, file_id = download_drive_file(service, "downloaded_urls.txt")
    pin_links = scrape_pinterest_links(query, 50)

    os.makedirs("temp_images", exist_ok=True)
    new_urls = set()

    for idx, pin in enumerate(pin_links):
        print(f"🔗 Visiting pin {idx + 1}/{len(pin_links)}: {pin}")
        img_url = get_image_from_pin(pin)

        if not img_url or img_url in downloaded_urls:
            print(f"⏩ Skipping already downloaded or no valid image: {img_url}")
            continue

        try:
            img_data = requests.get(img_url).content
            if not is_valid_image(img_data):
                print(f"❌ Low-quality or wrong aspect ratio: {img_url}")
                continue

            file_path = f"temp_images/{idx + 1}.jpg"
            with open(file_path, 'wb') as f:
                f.write(img_data)

            upload_image_to_drive(service, file_path, folder_id)
            os.remove(file_path)

            new_urls.add(img_url)
        except Exception as e:
            print(f"⚠️ Error downloading/uploading: {e}")

    # Update download history
    if new_urls:
        with open("downloaded_urls.txt", 'w') as f:
            f.write('\n'.join(downloaded_urls.union(new_urls)))
        upload_or_update_file(service, "downloaded_urls.txt", "downloaded_urls.txt", folder_id, file_id)

if __name__ == "__main__":
    main()
