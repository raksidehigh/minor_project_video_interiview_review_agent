"""
Workspace Management Utility
Handles isolated temp directories for each user with mandatory cleanup
"""
import os
import time
import shutil
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from google.cloud import storage

logger = logging.getLogger(__name__)


class UserWorkspace:
    """
    Isolated temporary workspace for a single user's assessment
    Ensures thread-safe resource management and mandatory cleanup
    """
    
    def __init__(self, user_id: str):
        """
        Create isolated workspace for user
        
        Args:
            user_id: User identifier (must be alphanumeric for safety)
        """
        # Sanitize user_id for filesystem safety
        self.user_id = "".join(c for c in user_id if c.isalnum() or c in "_-")
        self.timestamp = int(time.time() * 1000)  # millisecond precision
        
        # Create unique workspace directory
        base_temp = Path(tempfile.gettempdir()) / "video_assessments"
        base_temp.mkdir(exist_ok=True)
        
        self.workspace = base_temp / f"{self.user_id}_{self.timestamp}"
        self.workspace.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.videos_dir = self.workspace / "videos"
        self.audios_dir = self.workspace / "audios"
        self.images_dir = self.workspace / "images"
        
        self.videos_dir.mkdir(exist_ok=True)
        self.audios_dir.mkdir(exist_ok=True)
        self.images_dir.mkdir(exist_ok=True)
        
        logger.info(f"Created workspace: {self.workspace}")
    
    def get_video_path(self, index: int) -> Path:
        """Get path for video file"""
        return self.videos_dir / f"video{index}.webm"
    
    def get_audio_path(self, index: int) -> Path:
        """Get path for audio file"""
        return self.audios_dir / f"audio{index}.flac"
    
    def get_image_path(self, name: str) -> Path:
        """Get path for image file"""
        return self.images_dir / name
    
    def cleanup(self) -> Dict[str, any]:
        """
        MANDATORY cleanup with verification
        
        Returns:
            Cleanup report with verification status
        """
        cleanup_report = {
            "workspace": str(self.workspace),
            "user_id": self.user_id,
            "deleted": False,
            "verified": False,
            "errors": [],
            "files_deleted": 0
        }
        
        try:
            # Safety check: Verify workspace belongs to this user
            if self.user_id not in str(self.workspace):
                raise ValueError(
                    f"Safety check failed: Workspace {self.workspace} doesn't match user_id {self.user_id}"
                )
            
            # Count files before deletion
            file_count = sum(1 for _ in self.workspace.rglob("*") if _.is_file())
            cleanup_report["files_deleted"] = file_count
            
            # Delete directory and all contents
            if self.workspace.exists():
                shutil.rmtree(self.workspace, ignore_errors=False)
                cleanup_report["deleted"] = True
                logger.info(f"Deleted workspace: {self.workspace} ({file_count} files)")
            else:
                logger.warning(f"Workspace already deleted: {self.workspace}")
                cleanup_report["deleted"] = True
            
            # VERIFY deletion completed
            if self.workspace.exists():
                raise ValueError(f"Workspace {self.workspace} still exists after deletion!")
            
            cleanup_report["verified"] = True
            
            # Force garbage collection
            import gc
            gc.collect()
            
            logger.info(f"✅ Cleanup verified for user {self.user_id}")
            
        except Exception as e:
            error_msg = f"Cleanup failed for {self.user_id}: {str(e)}"
            logger.error(error_msg)
            cleanup_report["errors"].append(error_msg)
            
            # This is critical - log to monitoring
            logger.critical(f"CLEANUP FAILURE: {error_msg}")
        
        return cleanup_report
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup"""
        self.cleanup()
        return False


def download_from_gcs_sync(gcs_url: str, local_path: Path) -> Path:
    """
    Download file from GCS synchronously
    
    Args:
        gcs_url: GCS URL (gs://bucket/path)
        local_path: Local destination path
    
    Returns:
        Path to downloaded file
    """
    try:
        # Parse GCS URL
        if not gcs_url.startswith('gs://'):
            raise ValueError(f"Invalid GCS URL: {gcs_url}")
        
        parts = gcs_url[5:].split('/', 1)
        bucket_name = parts[0]
        blob_path = parts[1] if len(parts) > 1 else ''
        
        # Download from GCS
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        blob.download_to_filename(str(local_path))
        
        logger.info(f"Downloaded: {gcs_url} → {local_path.name}")
        return local_path
        
    except Exception as e:
        logger.error(f"Download failed: {gcs_url} - {str(e)}")
        raise


async def download_from_gcs(gcs_url: str, local_path: Path) -> Path:
    """
    Download file from GCS asynchronously
    
    Args:
        gcs_url: GCS URL (gs://bucket/path)
        local_path: Local destination path
    
    Returns:
        Path to downloaded file
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        download_from_gcs_sync,
        gcs_url,
        local_path
    )


async def download_videos_parallel(
    video_urls: List[str],
    workspace: UserWorkspace,
    max_workers: int = 5
) -> List[Path]:
    """
    Download all videos in parallel
    
    Args:
        video_urls: List of GCS URLs
        workspace: User workspace
        max_workers: Max parallel downloads
    
    Returns:
        List of local video paths
    """
    logger.info(f"Downloading {len(video_urls)} videos in parallel...")
    
    tasks = []
    for i, url in enumerate(video_urls, 1):
        local_path = workspace.get_video_path(i)
        tasks.append(download_from_gcs(url, local_path))
    
    video_paths = await asyncio.gather(*tasks)
    
    logger.info(f"✅ Downloaded {len(video_paths)} videos")
    return video_paths


async def prepare_user_resources(
    user_id: str,
    profile_pic_url: str,
    video_urls: List[str]
) -> Dict[str, any]:
    """
    Phase 1: Download all resources to isolated workspace
    
    Args:
        user_id: User identifier
        profile_pic_url: GCS URL to profile picture
        video_urls: List of 5 GCS URLs to videos (video_1-5 for interview)
    
    Returns:
        Dictionary with workspace and all local paths
    """
    logger.info(f"📥 PHASE 1: Preparing resources for user {user_id}")
    
    # Create isolated workspace
    workspace = UserWorkspace(user_id)
    
    try:
        # Download images and videos in parallel
        profile_pic_path = workspace.get_image_path("profile_pic.jpg")
        
        # Download everything in parallel
        download_tasks = [
            download_from_gcs(profile_pic_url, profile_pic_path),
            download_videos_parallel(video_urls, workspace)
        ]
        
        profile_pic, video_paths = await asyncio.gather(*download_tasks)
        
        logger.info(f"✅ PHASE 1 COMPLETE: All resources downloaded to {workspace.workspace}")
        
        return {
            "workspace": workspace,
            "profile_pic": profile_pic,
            "videos": video_paths,
            "video_count": len(video_paths)
        }
        
    except Exception as e:
        # Cleanup on failure
        logger.error(f"Resource preparation failed: {str(e)}")
        workspace.cleanup()
        raise


def verify_cleanup_before_response(cleanup_report: Dict) -> bool:
    """
    Verify cleanup was successful before sending response
    
    Args:
        cleanup_report: Report from workspace.cleanup()
    
    Returns:
        True if cleanup verified, False otherwise
    
    Raises:
        RuntimeError if cleanup failed (critical error)
    """
    if not cleanup_report.get("deleted"):
        raise RuntimeError(
            f"CRITICAL: Workspace deletion failed for {cleanup_report.get('user_id')}"
        )
    
    if not cleanup_report.get("verified"):
        raise RuntimeError(
            f"CRITICAL: Workspace deletion verification failed for {cleanup_report.get('user_id')}"
        )
    
    if cleanup_report.get("errors"):
        logger.error(f"Cleanup errors: {cleanup_report['errors']}")
        raise RuntimeError(
            f"CRITICAL: Cleanup completed with errors: {cleanup_report['errors']}"
        )
    
    logger.info(f"✅ Cleanup verified: {cleanup_report['files_deleted']} files deleted")
    return True

