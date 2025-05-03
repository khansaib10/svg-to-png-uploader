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
    decoded_bytes = base64.b64decode(base64_credentials)
    return json.loads(decoded_bytes)

# Setup Google Drive
def upload_to_drive(file_path, folder_id, credentials_json):
    SCOPES = ['https://www.googleapis.com/auth/drive.file']

    # Decode and load the credentials
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
    search_url = f"https://www.pinterest.com/search/pins/?q={query}"
    options = Options()
    options.headless = True
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
            if src and ('236x' not in src and '100x' not in src and '300x' not in src):  # avoid low-res thumbnails
                image_urls.add(src)

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    driver.quit()
    return list(image_urls)[:limit]

# Validate if an image is good quality (by checking its size and resolution)
def is_valid_image(img_data, min_size_kb=30, min_width=800, min_height=800):
    try:
        img = Image.open(BytesIO(img_data))
        img_size_kb = len(img_data) / 1024  # size in KB
        img_width, img_height = img.size
        if img_size_kb < min_size_kb:
            return False
        if img_width < min_width or img_height < min_height:
            return False
        return True
    except Exception as e:
        print(f"Error validating image: {e}")
        return False

# Main Function
def main():
    folder_id = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"  # Replace with your Google Drive folder ID
    queries = ["bike", "bike lovers", "Harley Davidson bike", "motorbike", "heavy bikes"]  # Multiple search queries
    download_limit = 100  # Number of images to download per query
    base64_credentials = os.getenv("SERVICE_ACCOUNT_BASE64")  # Get base64 credentials from environment variable

    # Create a temporary folder for downloaded images
    os.makedirs("temp_images", exist_ok=True)

    # Iterate over each keyword and scrape Pinterest images
    for query in queries:
        print(f"Scraping Pinterest for images with query: {query}")

        # Scrape Pinterest images for each keyword
        image_urls = scrape_pinterest_images(query, download_limit)

        if not image_urls:
            print(f"No images found for query '{query}'.")
            continue

        # Download and upload images to Google Drive
        for idx, url in enumerate(image_urls):
            print(f"Downloading image {idx + 1}/{len(image_urls)}: {url}")
            try:
                img_data = requests.get(url).content

                # Check if the image is valid (good size)
                if not is_valid_image(img_data):
                    print(f"Skipping low-quality image: {url}")
                    continue

                img_path = f"temp_images/{query}_{idx + 1}.jpg"  # Save images with the query name in the filename
                with open(img_path, 'wb') as handler:
                    handler.write(img_data)
                print(f"Downloaded {img_path}. Uploading to Google Drive...")
                upload_to_drive(img_path, folder_id, base64_credentials)
                os.remove(img_path)  # Clean up after upload
            except Exception as e:
                print(f"Error downloading {url}: {e}")

if __name__ == '__main__':
    main()
