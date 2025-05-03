import os
import time
import base64
import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image
from io import BytesIO

# Decode the base64-encoded credentials
def decode_credentials(base64_credentials):
    print("Decoding credentials...")
    decoded_bytes = base64.b64decode(base64_credentials)
    return json.loads(decoded_bytes)

# Setup Google Drive
def upload_to_drive(file_path, folder_id, credentials_json):
    print(f"Uploading {file_path} to Google Drive...")
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    credentials_dict = decode_credentials(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_dict, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)

    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/jpeg')

    file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded {file_path} to Google Drive. File ID: {file['id']}")

# Scrape Pinterest
def scrape_pinterest_images(query, limit=1000):
    print(f"Scraping Pinterest for images with query: {query}")
    search_url = f"https://www.pinterest.com/search/pins/?q={query}"
    options = Options()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)
    driver.get(search_url)
    time.sleep(5)

    image_urls = set()
    last_height = driver.execute_script("return document.body.scrollHeight")

    while len(image_urls) < limit:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and ('236x' not in src and '100x' not in src and '300x' not in src):
                image_urls.add(src)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    driver.quit()
    print(f"Scraping complete. Found {len(image_urls)} image URLs.")
    return list(image_urls)[:limit]

# Validate image: size + resolution + 9:16 aspect ratio
def is_valid_image(image_data, min_size_kb=20):
    image = Image.open(BytesIO(image_data))
    width, height = image.size
    size_kb = len(image_data) / 1024
    aspect_ratio = height / width if width else 0
    print(f"Checking image size: {size_kb:.2f} KB, Resolution: {width}x{height}, Ratio: {aspect_ratio:.2f}")
    return (
        size_kb >= min_size_kb and
        width > 500 and height > 500 and
        1.7 <= aspect_ratio <= 1.85
    )

# Main function
def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
    queries = ["bike", "bike lovers", "Harley Davidson bike", "motorbike", "heavy bikes"]
    download_limit = 100
    base64_credentials = os.getenv("SERVICE_ACCOUNT_BASE64")

    os.makedirs("temp_images", exist_ok=True)

    downloaded_urls = set()  # Store already downloaded URLs

    for query in queries:
        print(f"\nStarting keyword: {query}")
        image_urls = scrape_pinterest_images(query, download_limit)

        if not image_urls:
            print(f"No images found for query '{query}'.")
            continue

        for idx, url in enumerate(image_urls):
            if url in downloaded_urls:
                print(f"Skipping duplicate URL: {url}")
                continue

            print(f"Downloading image {idx + 1}/{len(image_urls)}: {url}")
            try:
                img_data = requests.get(url).content
                if not is_valid_image(img_data):
                    print("Skipping image: doesn't meet quality or ratio requirements.")
                    continue

                img_path = f"temp_images/{query}_{idx + 1}.jpg"
                with open(img_path, 'wb') as handler:
                    handler.write(img_data)

                upload_to_drive(img_path, folder_id, base64_credentials)
                os.remove(img_path)

                downloaded_urls.add(url)  # Mark as downloaded
            except Exception as e:
                print(f"Error downloading {url}: {e}")

if __name__ == '__main__':
    main()
