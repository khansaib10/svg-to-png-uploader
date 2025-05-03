import os
import io
import requests
import cairosvg
from bs4 import BeautifulSoup
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

# ----------------- Google Drive Auth ------------------
def authenticate_drive():
    gauth = GoogleAuth()
    gauth.LoadServiceConfigFile("service_account.json")
    gauth.Authorize()
    return GoogleDrive(gauth)

# ----------------- Get SVG URLs -----------------------
def get_svg_links(max_count=50):
    print("Scraping popular SVGs...")
    svg_urls = []
    page = 1
    while len(svg_urls) < max_count:
        url = f"https://www.svgrepo.com/vectors/popular/?page={page}"
        print(f"Fetching: {url}")
        r = requests.get(url)
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.select("a.download")
        if not links:
            break
        for link in links:
            href = link.get("href")
            if href and "/download/" in href:
                full_url = f"https://www.svgrepo.com{href}"
                svg_urls.append(full_url)
            if len(svg_urls) >= max_count:
                break
        page += 1
    print(f"Total SVGs found: {len(svg_urls)}")
    return svg_urls

# ----------------- Convert SVG to PNG -----------------
def convert_svg_to_png(svg_content):
    png_data = cairosvg.svg2png(bytestring=svg_content, output_width=1200, output_height=1600)
    return png_data

# ----------------- Upload to Google Drive -------------
def upload_to_drive(drive, png_bytes, filename, folder_id=None):
    file_drive = drive.CreateFile({
        'title': filename,
        'parents': [{'id': folder_id}] if folder_id else []
    })
    file_drive.SetContentString(png_bytes.decode('latin1'))
    file_drive.Upload()

# ----------------- Main Process -----------------------
def main():
    print("Authenticating Google Drive...")
    drive = authenticate_drive()

    svg_urls = get_svg_links(max_count=50)
    for idx, url in enumerate(svg_urls, 1):
        print(f"[{idx}] Downloading and converting: {url}")
        try:
            svg_response = requests.get(url.replace("/download", ""))
            if svg_response.status_code != 200:
                raise Exception(f"Failed to fetch SVG from: {url}")
            svg_content = svg_response.content
            if not svg_content.strip().startswith(b"<?xml") and b"<svg" not in svg_content:
                raise Exception("Downloaded file is not a valid SVG.")
            png_data = convert_svg_to_png(svg_content)
            filename = f"svg_image_{idx}.png"
            upload_to_drive(drive, png_data, filename)
        except Exception as e:
            print(f"Error converting {url}: {e}")

if __name__ == "__main__":
    print("Starting script...")
    main()
