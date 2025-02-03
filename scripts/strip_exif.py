#!/usr/bin/env python3
import sys
from pathlib import Path

from PIL import Image

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".webp"}


def strip_exif(image_path: Path) -> bool:
    """Strip EXIF data from an image file if present.
    Args:
        image_path: Path to the image file
    Returns:
        bool: True if successful, False if failed
    """
    try:
        with Image.open(image_path) as img:
            if not img.getexif():
                return True

            # Create a new image without EXIF
            data = list(img.getdata())
            img_without_exif = Image.new(img.mode, img.size)
            img_without_exif.putdata(data)
            img_without_exif.save(image_path, format=img.format)
            print(f"Stripped EXIF from: {image_path}")
            return True

    except Exception as e:
        print(f"Error processing {image_path}: {e}", file=sys.stderr)
        return False


def process_path(path: Path) -> None:
    """Process a single path, which may be a file or directory."""
    if path.is_file():
        if path.suffix.lower() in IMAGE_EXTENSIONS:
            strip_exif(path)
    elif path.is_dir():
        found_images = False
        for img_path in path.rglob("*"):
            if img_path.suffix.lower() in IMAGE_EXTENSIONS:
                found_images = True
                strip_exif(img_path)
        if not found_images:
            print(f"No images found in directory: {path}")


def main() -> None:
    """Main function to handle CLI usage."""
    if len(sys.argv) < 2:
        print(
            "Usage: strip_exif.py <file_or_directory> [file_or_directory ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    # Handle multiple paths
    for path_str in sys.argv[1:]:
        path = Path(path_str)
        if not path.exists():
            print(f"Path does not exist: {path}", file=sys.stderr)
            continue
        process_path(path)


if __name__ == "__main__":
    main()
