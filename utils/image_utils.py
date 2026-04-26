from io import BytesIO
import uuid
from PIL import Image, ImageOps


import boto3
from starlette.concurrency import run_in_threadpool
from config import settings

from botocore.exceptions import ClientError


# Get s3 client helper
def _get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=(
            settings.s3_access_key_id.get_secret_value()
            if settings.s3_access_key_id
            else None
        ),
        aws_secret_access_key=(
            settings.s3_secret_access_key.get_secret_value()
            if settings.s3_secret_access_key
            else None
        ),
        endpoint_url=settings.s3_endpoint_url,
    )


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

        output = BytesIO()
        img.save(output, format="JPEG", quality=85, optimize=True)
        output.seek(0)

    return output.read(), filename


# Upload to S3
def _upload_to_s3(file_bytes: bytes, key: str) -> str:
    s3_client = _get_s3_client()

    try:
        s3_client.upload_fileobj(
            BytesIO(file_bytes),
            settings.s3_bucket_name,
            key,
            ExtraArgs={"ContentType": "image/jpeg"},
        )
    except ClientError as e:
        raise RuntimeError(f"S3 upload failed: {e}")


# Delete from S3
def _delete_from_s3(key: str) -> None:
    s3_client = _get_s3_client()
    s3_client.delete_object(Bucket=settings.s3_bucket_name, Key=key)


async def upload_profile_image(file_bytes: bytes, filename: str) -> None:
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_upload_to_s3, file_bytes, key)


async def delete_profile_image(filename: str) -> None:
    if filename is None:
        return
    key = f"profile_pics/{filename}"
    await run_in_threadpool(_delete_from_s3, key)
