"""
Parallel Processing Utilities
Execute multiple tasks concurrently for faster processing
"""
import asyncio
import logging
from typing import List, Callable, Any, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logger = logging.getLogger(__name__)


async def process_videos_parallel(
    video_paths: List[Path],
    process_func: Callable,
    max_workers: int = 5,
    **kwargs
) -> List[Dict[str, Any]]:
    """
    Process multiple videos in parallel using ThreadPoolExecutor
    
    Args:
        video_paths: List of local video file paths
        process_func: Function to process each video (must be thread-safe)
        max_workers: Maximum number of parallel workers
        **kwargs: Additional arguments to pass to process_func
    
    Returns:
        List of results from process_func
    """
    logger.info(f"Processing {len(video_paths)} videos in parallel (max_workers={max_workers})")
    
    loop = asyncio.get_event_loop()
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_index = {}
        for i, video_path in enumerate(video_paths, 1):
            future = loop.run_in_executor(
                executor,
                process_func,
                video_path,
                i,
                kwargs
            )
            future_to_index[future] = i
        
        # Gather results
        completed_futures = await asyncio.gather(*future_to_index.keys(), return_exceptions=True)
        
        # Process results in order
        for i, result in enumerate(completed_futures, 1):
            if isinstance(result, Exception):
                logger.error(f"Video {i} processing failed: {str(result)}")
                results.append({
                    "video_index": i,
                    "error": str(result),
                    "success": False
                })
            else:
                results.append(result)
    
    success_count = sum(1 for r in results if r.get("success", False))
    logger.info(f"✅ Parallel processing complete: {success_count}/{len(video_paths)} succeeded")
    
    return results


async def process_items_parallel(
    items: List[Any],
    process_func: Callable,
    max_workers: int = 5
) -> List[Any]:
    """
    Generic parallel processing for any list of items
    
    Args:
        items: List of items to process
        process_func: Function to process each item
        max_workers: Maximum number of parallel workers
    
    Returns:
        List of results
    """
    loop = asyncio.get_event_loop()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [
            loop.run_in_executor(executor, process_func, item)
            for item in items
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    return results


def run_sync_in_parallel(func: Callable, items: List[Any], max_workers: int = 5) -> List[Any]:
    """
    Synchronous version of parallel processing (for non-async contexts)
    
    Args:
        func: Function to execute
        items: List of items to process
        max_workers: Maximum number of parallel workers
    
    Returns:
        List of results
    """
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(func, item): item for item in items}
        
        for future in as_completed(future_to_item):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Task failed: {str(e)}")
                results.append({"error": str(e), "success": False})
    
    return results


class ParallelTaskManager:
    """
    Manage multiple parallel tasks with progress tracking
    """
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.completed = 0
        self.total = 0
        self.results = []
    
    async def run_tasks(
        self,
        tasks: List[Callable],
        task_names: List[str] = None
    ) -> List[Any]:
        """
        Run multiple async tasks in parallel
        
        Args:
            tasks: List of coroutines to execute
            task_names: Optional names for logging
        
        Returns:
            List of results
        """
        self.total = len(tasks)
        self.completed = 0
        
        if task_names is None:
            task_names = [f"Task {i+1}" for i in range(len(tasks))]
        
        logger.info(f"Starting {self.total} parallel tasks...")
        
        # Execute all tasks
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Track results
        for i, (result, name) in enumerate(zip(results, task_names)):
            if isinstance(result, Exception):
                logger.error(f"{name} failed: {str(result)}")
            else:
                logger.info(f"{name} completed")
            self.completed += 1
        
        logger.info(f"✅ All {self.total} tasks completed")
        
        return results
    
    def get_progress(self) -> Dict[str, any]:
        """Get current progress"""
        return {
            "completed": self.completed,
            "total": self.total,
            "percentage": (self.completed / self.total * 100) if self.total > 0 else 0
        }

