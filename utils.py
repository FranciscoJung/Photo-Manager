import hashlib
import shutil
import os
from PIL import Image
from datetime import datetime

# BASE_DIR será sobrescrito pelo main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

THUMB_SIZE = (200, 200)

def get_photos_dir():
    return os.path.join(BASE_DIR, "photos")

def get_thumbs_dir():
    return os.path.join(BASE_DIR, "thumbnails")

def ensure_dirs():
    os.makedirs(get_photos_dir(), exist_ok=True)
    os.makedirs(get_thumbs_dir(), exist_ok=True)

def get_file_hash(filepath: str) -> str:
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def import_photo(source_path: str):
    file_hash = get_file_hash(source_path)
    ext = os.path.splitext(source_path)[1].lower()
    new_filename = f"{file_hash}{ext}"
    dest_path = os.path.join(get_photos_dir(), new_filename)

    if os.path.exists(dest_path):
        return None

    shutil.copy2(source_path, dest_path)
    generate_thumbnail(new_filename)
    return file_hash, new_filename

def generate_thumbnail(filename: str):
    source = os.path.join(get_photos_dir(), filename)
    dest = os.path.join(get_thumbs_dir(), filename)
    if not os.path.exists(dest):
        with Image.open(source) as img:
            img.thumbnail(THUMB_SIZE)
            img.save(dest)

def get_exif_date(filepath: str):
    try:
        with Image.open(filepath) as img:
            exif_data = img._getexif()
            if exif_data and 36867 in exif_data:
                raw = exif_data[36867]
                dt = datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return None