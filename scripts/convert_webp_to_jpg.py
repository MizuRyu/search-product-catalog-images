# python scripts/convert_webp_to_jpg.py

import os
from PIL import Image

def convert_webp_to_jpg(image_dir: str) -> None:
    for filename in os.listdir(image_dir):
        if filename.lower().endswith('.webp'):
            webp_path = os.path.join(image_dir, filename)
            jpg_path = os.path.splitext(webp_path)[0] + '.jpg'

            if os.path.exists(jpg_path):
                print(f"Skipping {webp_path} as {jpg_path} already exists.")
                continue

            with Image.open(webp_path) as img:
                img.convert('RGB').save(jpg_path, 'JPEG')
            
            os.remove(webp_path)

            print(f"Converted {webp_path} to {jpg_path}")

if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(__file__))
    image_dir = os.path.join(root_dir, 'images')
    convert_webp_to_jpg(image_dir)