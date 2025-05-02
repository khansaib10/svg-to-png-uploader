import os
import requests
import time
from bs4 import BeautifulSoup
from PIL import Image
import cairosvg
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Define the Google Drive folder ID
DRIVE_FOLDER_ID = '1jnHnezrLNTl3ebmlt2QRBDSQplP_Q4wh'  # Replace with your folder ID

# Path to the service account credentials file
SERVICE_ACCOUNT_FILE = 'service_account.json'

# Define the directory for downloading the SVG files
DOWNLOAD_DIR = 'downloads'

# Create the directory if it doesn't exist
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# Initialize the Google Drive API client
def get_drive_service():
    print("Initializing Google Drive service...")
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/drive.file"])
    drive_service = build('drive', 'v3', credentials=creds)
    return drive_service

# Function to upload files to Google Drive
def upload_file_to_drive(file_path, folder_id):
    print(f"Uploading {file_path} to Google Drive folder {folder_id}...")
    drive_service = get_drive_service()
    file_metadata = {'name': os.path.basename(file_path), 'parents': [folder_id]}
    media = MediaFileUpload(file_path, mimetype='image/png')
    try:
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"Successfully uploaded {file_path} with file ID: {file['id']}")
    except Exception as e:
        print(f"Error uploading {file_path}: {e}")

# Function to convert SVG to PNG
def convert_svg_to_png(svg_file_path, png_file_path):
    print(f"Converting {svg_file_path} to {png_file_path}...")
    cairosvg.svg2png(url=svg_file_path, write_to=png_file_path)
    print(f"Successfully converted {svg_file_path} to {png_file_path}")

# Function to scrape SVGRepo for SVG links
def scrape_svgrepo_svg_links(limit=5000, retries=3):
    base_url = 'https://www.svgrepo.com'
    svg_links = []
    page = 1

    while len(svg_links) < limit:
        print(f"Scraping SVGRepo page {page}...")
        url = f"{base_url}/svg/{page}/"

        attempt = 0
        while attempt < retries:
            try:
                print(f"Fetching: {url}")
                response = requests.get(url, timeout=30)  # Increased timeout
                if response.status_code == 200:
                    print(f"Successfully loaded page {page}")
                    soup = BeautifulSoup(response.text, 'html.parser')
                    icons = soup.select("a[href^='/download/']")
                    for a in icons:
                        href = a.get("href")
                        if href.endswith(".svg"):
                            svg_links.append(base_url + href)
                    page += 1
                    break
                else:
                    print(f"Failed to load page {page}. Status code: {response.status_code}")
                    time.sleep(5)
            except requests.exceptions.RequestException as e:
                print(f"Request failed for page {page}: {e}")
                attempt += 1
                time.sleep(5)

        if attempt == retries:
            print(f"Giving up on page {page} after {retries} attempts.")
            break

    print(f"Found {len(svg_links)} SVG links.")
    return svg_links

# Function to download SVG files
def download_svg(svg_url, filename):
    print(f"Downloading SVG: {svg_url}...")
    try:
        response = requests.get(svg_url)
        if response.status_code == 200:
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"Downloaded SVG to {filename}")
        else:
            print(f"Failed to download {svg_url}. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {svg_url}: {e}")

# Main function to orchestrate the download, convert, and upload process
def main():
    print("Starting script...")
    svg_links = scrape_svgrepo_svg_links(limit=5000)

    # Download, convert, and upload the SVGs
    for index, svg_url in enumerate(svg_links):
        print(f"Processing SVG {index + 1} of {len(svg_links)}...")
        try:
            svg_filename = os.path.join(DOWNLOAD_DIR, f"image_{index + 1}.svg")
            download_svg(svg_url, svg_filename)

            png_filename = svg_filename.replace('.svg', '.png')
            convert_svg_to_png(svg_filename, png_filename)

            upload_file_to_drive(png_filename, DRIVE_FOLDER_ID)

            # Optional: Clean up downloaded SVG and PNG files after upload
            os.remove(svg_filename)
            os.remove(png_filename)

            print(f"Completed processing for image {index + 1}.")
        except Exception as e:
            print(f"Error processing SVG {index + 1}: {e}")

    print("Script completed.")

if __name__ == "__main__":
    main()
