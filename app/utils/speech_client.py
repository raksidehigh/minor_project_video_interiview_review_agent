"""
Singleton Speech-to-Text V2 Client Manager
Ensures client is loaded only once and reused across all user assessments
"""
import os
from typing import Optional
from google.cloud.speech_v2 import SpeechClient
from google.api_core.client_options import ClientOptions


class SpeechClientManager:
    """
    Singleton manager for Speech-to-Text V2 clients
    Initializes clients once and reuses them across all requests
    """
    _instances = {}  # Dict to cache clients by region
    _lock = None  # Threading lock for thread safety
    
    @classmethod
    def get_client(cls, region: str = "us") -> SpeechClient:
        """
        Get or create a Speech-to-Text V2 client for the specified region
        
        Args:
            region: Google Cloud region (us, eu, asia-southeast1, asia-northeast1)
        
        Returns:
            SpeechClient instance (cached/singleton)
        """
        # Thread-safe singleton pattern
        if cls._lock is None:
            import threading
            cls._lock = threading.Lock()
        
        # Check if client already exists for this region
        if region in cls._instances:
            return cls._instances[region]
        
        # Create new client with lock to prevent race conditions
        with cls._lock:
            # Double-check pattern (another thread might have created it)
            if region in cls._instances:
                return cls._instances[region]
            
            # Create new client
            client = SpeechClient(
                client_options=ClientOptions(
                    api_endpoint=f"{region}-speech.googleapis.com",
                )
            )
            
            # Cache the client
            cls._instances[region] = client
            print(f"[SPEECH_CLIENT] Initialized new Speech V2 client for region: {region}")
            
            return client
    
    @classmethod
    def get_project_id(cls) -> str:
        """
        Get Google Cloud Project ID from environment or default credentials
        Cached for efficiency
        """
        if not hasattr(cls, '_project_id'):
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            if not project_id:
                # Try to get from credentials
                try:
                    from google.auth import default
                    _, project_id = default()
                except Exception:
                    pass
            
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT environment variable must be set")
            
            cls._project_id = project_id
            print(f"[SPEECH_CLIENT] Project ID: {project_id}")
        
        return cls._project_id
    
    @classmethod
    def clear_cache(cls):
        """Clear cached clients (useful for testing or region switching)"""
        cls._instances.clear()
        if hasattr(cls, '_project_id'):
            delattr(cls, '_project_id')
        print("[SPEECH_CLIENT] Cache cleared")

