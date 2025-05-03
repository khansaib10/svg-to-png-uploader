import os
import io
import time
import requests
import cairosvg
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# -------------- CONFIGURATION --------------
KEYWORDS       = ["bike","nature","cat","mountain","flower"]
MAX_PER_KEY    = 5          # how many SVGs per keyword
PAGE_DELAY     = 2          # seconds to wait for each page load
SERVICE_ACCOUNT_FILE = "service_account.json"
DRIVE_FOLDER_ID      = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"
# -------------------------------------------

def authenticate_drive():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build("drive","v3",credentials=creds)

def get_download_links_for_keyword(keyword):
    opts   = Options(); opts.add_argument("--headless"); opts.add_argument("--no-sandbox")
    service= Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service,options=opts)

    found = []
    page  = 1
    while len(found) < MAX_PER_KEY:
        url = f"https://www.svgrepo.com/search/{keyword}/?page={page}"
        print(f"→ loading search page: {url}")
        driver.get(url)
        time.sleep(PAGE_DELAY)

        # find all anchors pointing to direct .svg downloads
        els = driver.find_elements(
            By.XPATH,
            "//a[contains(@href,'/download/') and contains(@href,'.svg')]"
        )
        for e in els:
            href = e.get_attribute("href")
            if href not in found:
                found.append(href)
            if len(found) >= MAX_PER_KEY:
                break

        # if no new links, break
        if not els or page>10:
            break
        page += 1

    driver.quit()
    print(f"• {len(found)} SVG URLs for '{keyword}'")
    return found

def download_and_convert(svg_url):
    print(f"Downloading SVG: {svg_url}")
    r = requests.get(svg_url, timeout=10)
    if r.status_code!=200 or b"<svg" not in r.content[:100]:
        print(" ⚠️ bad SVG, skipping")
        return None
    # convert to PNG bytes
    return cairosvg.svg2png(bytestring=r.content, output_width=1200, output_height=1600)

def upload_png(data, name, drive):
    print(f"Uploading {name}...")
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="image/png")
    meta  = {"name":name, "parents":[DRIVE_FOLDER_ID]}
    drive.files().create(body=meta, media_body=media, fields="id").execute()
    print(f" ✔️ {name} uploaded")

def main():
    drive = authenticate_drive()
    count = 0

    for kw in KEYWORDS:
        links = get_download_links_for_keyword(kw)
        for url in links:
            filename = url.split("/")[-1].replace(".svg",".png")
            pngdata  = download_and_convert(url)
            if pngdata:
                upload_png(pngdata, f"{kw}_{filename}", drive)
                count += 1
            if count >= MAX_PER_KEY * len(KEYWORDS):
                break
        if count >= MAX_PER_KEY * len(KEYWORDS):
            break

    print("All done.")

if __name__=="__main__":
    main()
