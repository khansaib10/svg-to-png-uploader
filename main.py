import os
import time
import requests
from io import BytesIO
from PIL import Image
import cairosvg
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- Config ---
SVGREPO_API_KEY = os.getenv("SVGREPO_API_KEY")
DRIVE_FOLDER_ID = os.getenv("DRIVE_FOLDER_ID")

if not SVGREPO_API_KEY or not DRIVE_FOLDER_ID:
    raise Exception("Missing SVGREPO_API_KEY or DRIVE_FOLDER_ID env variable")

# --- Google Drive Auth ---
def auth_drive():
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build("drive", "v3", credentials=creds)

def upload_to_drive(filepath, filename):
    service = auth_drive()
    file_metadata = {
        "name": filename,
        "parents": [DRIVE_FOLDER_ID],
    }
    media = MediaFileUpload(filepath, mimetype="image/png")
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()
    return uploaded_file.get("id")

# --- Download SVGs from SVGRepo ---
def get_random_svgs(limit=10):
    url = f"https://www.svgrepo.com/api/v1/search/?query=vector&limit={limit}"
    headers = {"Authorization": f"Token {SVGREPO_API_KEY}"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json().get("data", [])

# --- Convert and Upload ---
def process_svg(svg_info):
    svg_url = svg_info.get("url")
    if not svg_url:
        return None

    print("Downloading SVG:", svg_url)
    svg_response = requests.get(svg_url, timeout=10)
    svg_response.raise_for_status()

    filename_base = f"svg_{int(time.time() * 1000)}"
    svg_path = f"{filename_base}.svg"
    png_path = f"{filename_base}.png"

    # Save SVG locally
    with open(svg_path, "wb") as f:
        f.write(svg_response.content)

    # Convert to PNG
    try:
        cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=1200, output_height=1600)
    except Exception as e:
        print("Conversion failed:", e)
        return None

    # Upload to Google Drive
    file_id = upload_to_drive(png_path, os.path.basename(png_path))
    print("Uploaded file ID:", file_id)

    # Clean up
    os.remove(svg_path)
    os.remove(png_path)

    return file_id

# --- Main ---
def main():
    svg_list = get_random_svgs(limit=10)  # You can change to 50 or 100 per batch
    print(f"Found {len(svg_list)} SVGs")

    for svg in svg_list:
        process_svg(svg)

if __name__ == "__main__":
    main()
