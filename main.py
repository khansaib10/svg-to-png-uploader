import requests
import cairosvg
import os
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from googleapiclient.http import MediaFileUpload

# Function to authenticate Google Drive
def authenticate_drive():
    print("Authenticating Google Drive...")
    credentials = service_account.Credentials.from_service_account_file(
        'service_account.json', scopes=['https://www.googleapis.com/auth/drive.file']
    )
    drive_service = build('drive', 'v3', credentials=credentials)
    return drive_service

# Function to get SVG links using Selenium
def get_svg_links(max_count=50):
    print("Scraping popular SVGs...")
    svg_urls = []
    page = 1

    # Setup Selenium WebDriver (headless mode)
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(ChromeDriverManager().install(), options=chrome_options)

    while len(svg_urls) < max_count:
        url = f"https://www.svgrepo.com/vectors/popular/{page}/"
        print(f"Fetching: {url}")
        driver.get(url)
        time.sleep(3)  # Let the page load fully

        # Get all SVG download links from the page
        cards = driver.find_elements_by_css_selector('a[href^="/svg/"]')
        for card in cards:
            href = card.get_attribute("href")
            if href and href.startswith("https://www.svgrepo.com/svg/") and href.count("/") == 4:
                download_url = f"{href}download/"
                svg_urls.append(download_url)
                if len(svg_urls) >= max_count:
                    break

        if len(svg_urls) < max_count:
            page += 1
        else:
            break

    driver.quit()
    print(f"Total SVGs found: {len(svg_urls)}")
    return svg_urls

# Function to download an SVG and convert to PNG
def download_and_convert_svg(svg_url, output_folder):
    print(f"Downloading: {svg_url}")
    response = requests.get(svg_url)
    svg_filename = svg_url.split('/')[-2] + '.svg'
    svg_path = os.path.join(output_folder, svg_filename)

    with open(svg_path, 'wb') as file:
        file.write(response.content)

    png_path = svg_path.replace('.svg', '.png')
    cairosvg.svg2png(url=svg_path, write_to=png_path)
    return png_path

# Function to upload PNG to Google Drive
def upload_to_drive(file_path, drive_service):
    file_metadata = {'name': os.path.basename(file_path)}
    media = MediaFileUpload(file_path, mimetype='image/png')

    file = drive_service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()
    print(f"Uploaded {os.path.basename(file_path)} to Google Drive")
    return file['id']

# Main function
def main():
    output_folder = "downloaded_svgs"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Authenticate Google Drive
    drive_service = authenticate_drive()

    # Get SVG links
    svg_links = get_svg_links(max_count=10)  # Adjust max_count as necessary

    for svg_link in svg_links:
        # Download and convert SVG to PNG
        png_path = download_and_convert_svg(svg_link, output_folder)

        # Upload PNG to Google Drive
        upload_to_drive(png_path, drive_service)

    print("Script completed!")

if __name__ == "__main__":
    main()
