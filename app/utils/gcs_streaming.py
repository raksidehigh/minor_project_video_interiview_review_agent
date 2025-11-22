"""
Google Cloud Storage Streaming Utilities
Stream videos directly from GCS without downloading to disk
"""
import tempfile
import datetime
from typing import Optional
from google.cloud import storage
import google.auth
from google.auth.transport import requests as google_requests


def get_signed_url(gcs_url: str, expiration_minutes: int = 60) -> str:
    """
    Generate a signed URL for direct access to GCS file
    Uses service account key for signing (works everywhere!)
    
    Args:
        gcs_url: GCS URL (gs://bucket/path/to/file)
        expiration_minutes: URL expiration time in minutes (default: 60)
    
    Returns:
        HTTPS signed URL that can be accessed directly
    
    Example:
        >>> signed_url = get_signed_url("gs://my-bucket/video.mp4")
        >>> cap = cv2.VideoCapture(signed_url)  # Stream directly! NO DOWNLOAD!
    """
    if not gcs_url.startswith('gs://'):
        # If local file or already HTTP URL, return as-is
        return gcs_url
    
    # Parse GCS URL: gs://bucket/path/to/file
    parts = gcs_url.replace('gs://', '').split('/', 1)
    bucket_name = parts[0]
    blob_path = parts[1]
    
    # Create storage client (will use GOOGLE_APPLICATION_CREDENTIALS env var)
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    try:
        # Simple signing with service account key
        print(f"         🔑 Signing URL with service account key...")
        
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=expiration_minutes),
            method="GET"
        )
        
        return signed_url
        
    except Exception as e:
        error_msg = f"Failed to generate signed URL: {str(e)}"
        print(f"         ❌ {error_msg}")
        raise Exception(error_msg)


def download_small_file(gcs_url: str) -> str:
    """
    Download small files (images) that need to be saved temporarily
    Used only for small images (profile pics, gov IDs)
    
    Args:
        gcs_url: GCS URL (gs://bucket/path/to/file)
    
    Returns:
        Local temp file path
    
    Note:
        Only use this for small files like images (< 1MB)
        For videos, use get_signed_url() and stream instead!
    """
    if not gcs_url.startswith('gs://'):
        return gcs_url
    
    # Parse GCS URL
    parts = gcs_url.replace('gs://', '').split('/', 1)
    bucket_name = parts[0]
    blob_path = parts[1]
    
    # Download to temp file
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    # Get file extension
    import os
    _, ext = os.path.splitext(blob_path)
    
    # Create temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    blob.download_to_filename(temp_file.name)
    
    return temp_file.name


def stream_video_info(gcs_url: str) -> dict:
    """
    Get video metadata without downloading
    
    Args:
        gcs_url: GCS URL (gs://bucket/path/to/file)
    
    Returns:
        dict with size, content_type, etc.
    """
    if not gcs_url.startswith('gs://'):
        return {"error": "Not a GCS URL"}
    
    parts = gcs_url.replace('gs://', '').split('/', 1)
    bucket_name = parts[0]
    blob_path = parts[1]
    
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    
    # Reload to get metadata
    blob.reload()
    
    return {
        "name": blob.name,
        "size_mb": blob.size / (1024 * 1024) if blob.size else 0,
        "content_type": blob.content_type,
        "created": blob.time_created.isoformat() if blob.time_created else None,
        "updated": blob.updated.isoformat() if blob.updated else None
    }

