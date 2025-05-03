import os
import io
import time
import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ---------- SETTINGS ----------
KEYWORDS = ["ai girl", "ai girl"]  # You can add more
GOOGLE_DRIVE_FOLDER_ID = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
SERVICE_ACCOUNT_FILE = "service_account.json"
DOWNLOADED_RECORD_FILE = "downloaded_images.txt"
MAX_IMAGES_PER_KEYWORD = 100
HEADLESS = True
SCROLL_PAUSE = 2
SCROLL_TIMES = 3
# -----------------------------

# Load downloaded URLs to avoid duplicates
downloaded = set()
if os.path.exists(DOWNLOADED_RECORD_FILE):
    with open(DOWNLOADED_RECORD_FILE, "r") as f:
        downloaded = set(line.strip() for line in f)

# Setup Google Drive
creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE,
    scopes=['https://www.googleapis.com/auth/drive']
)
drive_service = build('drive', 'v3', credentials=creds)

def upload_to_drive(image_bytes, filename):
    media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype='image/jpeg')
    file_metadata = {
        'name': filename,
        'parents': [GOOGLE_DRIVE_FOLDER_ID]
    }
    drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

# Setup Selenium
options = Options()
if HEADLESS:
    options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)

def scroll_page():
    for _ in range(SCROLL_TIMES):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)

def is_portrait(img):
    return img.height > img.width

def process_keyword(keyword):
    print(f"Processing keyword: {keyword}")
    driver.get(f"https://www.pinterest.com/search/pins/?q={keyword.replace(' ', '%20')}")
    time.sleep(3)
    scroll_page()

    pins = driver.find_elements(By.CSS_SELECTOR, 'a[href^="/pin/"]')
    links = list({p.get_attribute("href") for p in pins if p.get_attribute("href")})
    links = [l for l in links if "/pin/" in l][:MAX_IMAGES_PER_KEYWORD * 2]

    downloaded_this_round = 0

    for link in links:
        if downloaded_this_round >= MAX_IMAGES_PER_KEYWORD:
            break
        try:
            full_url = link if link.startswith("http") else f"https://www.pinterest.com{link}"
            if full_url in downloaded:
                continue

            driver.get(full_url)
            time.sleep(2)

            img_tag = driver.find_element(By.CSS_SELECTOR, "img[srcset]")
            img_url = img_tag.get_attribute("src")

            if img_url in downloaded:
                continue

            response = requests.get(img_url)
            if response.status_code != 200:
                continue

            img = Image.open(io.BytesIO(response.content)).convert("RGB")
            if not is_portrait(img):
                continue

            filename = f"{keyword.replace(' ', '_')}_{int(time.time())}.jpg"
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")
            buffer.seek(0)

            upload_to_drive(buffer.read(), filename)

            with open(DOWNLOADED_RECORD_FILE, "a") as f:
                f.write(img_url + "\n")
            downloaded.add(img_url)

            downloaded_this_round += 1
            print(f"Uploaded: {filename}")
        except Exception as e:
            print(f"Skipped due to error: {e}")
            continue

# Main loop
for keyword in KEYWORDS:
    process_keyword(keyword)

driver.quit()
