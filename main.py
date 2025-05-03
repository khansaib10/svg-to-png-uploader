import os
import requests
from bs4 import BeautifulSoup
from cairosvg import svg2png
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from io import BytesIO
from PIL import Image

# Google Drive folder ID
FOLDER_ID = "1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh"

# Authenticate Google Drive
print("Authenticating Google Drive...")
ga = GoogleAuth()
ga.LocalWebserverAuth()
drive = GoogleDrive(ga)


def upload_to_drive(image_data, filename):
    print(f"Uploading {filename} to Google Drive...")
    file = drive.CreateFile({'title': filename, 'parents': [{'id': FOLDER_ID}]})
    image_data.seek(0)
    file.SetContentFile(filename)
    with open(filename, "wb") as f:
        f.write(image_data.read())
    file.Upload()
    os.remove(filename)


def fetch_svg_file(svg_page_url):
    try:
        print(f"Visiting SVG page: {svg_page_url}")
        page = requests.get(svg_page_url)
        if page.status_code != 200:
            print(f"Failed to load SVG page: {svg_page_url}")
            return None
        soup = BeautifulSoup(page.text, "html.parser")
        download_btn = soup.find("a", string="SVG")
        if download_btn and download_btn["href"].endswith(".svg"):
            svg_url = download_btn["href"]
            if svg_url.startswith("/"):
                svg_url = "https://www.svgrepo.com" + svg_url
            print(f"Found SVG file: {svg_url}")
            svg_response = requests.get(svg_url)
            if svg_response.status_code == 200:
                return svg_response.content
            else:
                print(f"Failed to download raw SVG from {svg_url}")
        else:
            print("SVG download link not found on the page.")
    except Exception as e:
        print(f"Exception while fetching SVG file: {e}")
    return None


def convert_and_upload(svg_content, index):
    try:
        png_output = BytesIO()
        svg2png(bytestring=svg_content, write_to=png_output, output_width=1200, output_height=1600, background_color=None)
        png_output.seek(0)
        filename = f"design_{index}.png"
        upload_to_drive(png_output, filename)
    except Exception as e:
        print(f"Error converting SVG to PNG: {e}")


print("Starting script...")
print("Starting batch: 0 to 50")

# Scrape popular SVGs
print("Scraping popular SVGs...")
svg_links = []
for page in range(1, 5):
    print(f"Fetching: https://www.svgrepo.com/vectors/popular/?page={page}")
    r = requests.get(f"https://www.svgrepo.com/vectors/popular/?page={page}")
    soup = BeautifulSoup(r.text, "html.parser")
    grid = soup.find_all("a", class_="svg-preview")
    if not grid:
        print("No more SVGs found.")
        break
    for link in grid:
        href = link.get("href")
        if href and href.startswith("/svg"):
            svg_links.append("https://www.svgrepo.com" + href)
    if len(svg_links) >= 50:
        break

print(f"Total SVGs found: {len(svg_links)}")

# Process and upload
for i, svg_page_url in enumerate(svg_links[:50]):
    print(f"[{i+1}] Downloading and converting: {svg_page_url}")
    svg_content = fetch_svg_file(svg_page_url)
    if svg_content:
        convert_and_upload(svg_content, i+1)
    else:
        print(f"Skipping {svg_page_url} due to fetch error.")
