from io import BytesIO
from pathlib import Path
import uuid
from PIL import Image, ImageOps

PROFILE_PICS_DIR = Path("media/profile_pics")


# Process image
def process_profile_image(content: bytes) -> str:
    with Image.open(BytesIO(content)) as original:
        img = ImageOps.exif_transpose(original)

        # Resize the image to 300x300 pixels while maintaining aspect ratio
        img = ImageOps.fit(img, (300, 300), method=Image.Resampling.LANCZOS)

        # Convert to RGB if needed
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")

        # Generate a unique filename
        filename = f"{uuid.uuid4().hex}.jpg"

        FILE_PATH = PROFILE_PICS_DIR / filename

        PROFILE_PICS_DIR.mkdir(parents=True, exist_ok=True)

        img.save(FILE_PATH, format="JPEG", quality=85, optimize=True)

    return filename


# helper for deleting old profile picture
def delete_profile_image(filename: str | None) -> None:
    if filename is None:
        return

    filepath = PROFILE_PICS_DIR / Path(filename).name
    if filepath.exists():
        filepath.unlink()
