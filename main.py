import os
import time
import base64
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Decode credentials
def decode_credentials(b64):
    return json.loads(base64.b64decode(b64))

# Load/save duplicates
def load_downloaded_urls():
    return set(open("downloaded_urls.txt").read().splitlines()) if os.path.exists("downloaded_urls.txt") else set()
def save_downloaded_urls(urls):
    open("downloaded_urls.txt","w").write("\n".join(urls))

# Upload to Drive
def upload_to_drive(path, folder_id, drive):
    meta = {'name':os.path.basename(path),'parents':[folder_id]}
    media = MediaFileUpload(path, mimetype='image/jpeg')
    drive.files().create(body=meta, media_body=media, fields='id').execute()

# Simple portrait filter
def is_portrait(image_data):
    try:
        w,h = Image.open(BytesIO(image_data)).size
        return h> w
    except:
        return False

def scrape_pins(query, limit=50):
    url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ','%20')}"
    opts = Options()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=opts)
    driver.get(url)
    time.sleep(5)  # let top pins load

    # grab first 50 pin links without scrolling
    elems = driver.find_elements(By.CSS_SELECTOR,'a[href*="/pin/"]')
    pin_links = []
    for e in elems:
        href = e.get_attribute("href").split('?')[0]
        if href not in pin_links:
            pin_links.append(href)
        if len(pin_links)>=limit:
            break

    print(f"Found {len(pin_links)} top pins.")
    results = []
    for link in pin_links:
        try:
            driver.get(link)
            WebDriverWait(driver,10).until(EC.presence_of_element_located((By.TAG_NAME,'head')))
            soup = BeautifulSoup(driver.page_source,'html.parser')
            meta = soup.find('meta',property='og:image')
            if meta:
                src = meta['content']
                if src not in results:
                    results.append(src)
                    print("✅", src)
            if len(results)>=limit:
                break
        except Exception as e:
            print("⚠️", link, e)

    driver.quit()
    return results

def download_duplicates_file(drive, folder_id):
    q = f"'{folder_id}' in parents and name='downloaded_urls.txt' and trashed=false"
    res = drive.files().list(q=q, fields='files(id)').execute().get('files',[])
    if res:
        fid = res[0]['id']
        req = drive.files().get_media(fileId=fid)
        with open('downloaded_urls.txt','wb') as f:
            downloader = MediaIoBaseDownload(f,req)
            done=False
            while not done:
                _,done = downloader.next_chunk()
        return fid
    return None

def upload_duplicates_file(drive, folder_id, file_id):
    media = MediaFileUpload('downloaded_urls.txt',mimetype='text/plain')
    meta = {'name':'downloaded_urls.txt','parents':[folder_id]}
    if file_id:
        drive.files().update(fileId=file_id, media_body=media).execute()
    else:
        drive.files().create(body=meta, media_body=media, fields='id').execute()

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
    os.makedirs("temp_images",exist_ok=True)

    for q in queries:
        urls = scrape_pins(q,limit)
        for i,url in enumerate(urls,1):
            if url in downloaded:
                print("⏩ duplicate",url); continue
            print("⬇️",url)
            try:
                data = requests.get(url,timeout=10).content
                if not is_portrait(data):
                    print("⚠️ not portrait",url); continue
                path = f"temp_images/{q}_{i}.jpg"
                open(path,'wb').write(data)
                upload_to_drive(path,folder_id,drive)
                downloaded.add(url)
                os.remove(path)
            except Exception as e:
                print("❌",e)

    save_downloaded_urls(downloaded)
    upload_duplicates_file(drive,folder_id,dup_id)

if __name__=='__main__':
    main()
