"""
Webhook Client for Human-in-Loop Integration
Sends notifications for identity failures and other review-required cases
"""
import os
import logging
from typing import Dict, Any
import aiohttp
import asyncio

logger = logging.getLogger(__name__)


class WebhookClient:
    """Client for sending webhook notifications to admin panel"""
    
    def __init__(self, base_url: str = None):
        """
        Initialize webhook client
        
        Args:
            base_url: Base URL for webhook endpoints (defaults to env var WEBHOOK_BASE_URL)
        """
        self.base_url = base_url or os.getenv('WEBHOOK_BASE_URL', 'http://localhost:8000')
        self.timeout = aiohttp.ClientTimeout(total=10)  # 10 second timeout
    
    async def send_identity_failure(
        self,
        user_id: str,
        username: str,
        identity_data: Dict[str, Any],
        assessment_id: str = None
    ) -> bool:
        """
        Send identity failure notification for human review
        
        Args:
            user_id: User identifier
            username: User's name
            identity_data: Identity verification results
            assessment_id: Assessment identifier (optional)
        
        Returns:
            True if webhook sent successfully, False otherwise
        """
        endpoint = f"{self.base_url}/api/webhooks/identity-failure"
        
        payload = {
            "user_id": user_id,
            "username": username,
            "assessment_id": assessment_id or user_id,
            "identity_verification": {
                "verified": identity_data.get('verified', False),
                "confidence": identity_data.get('confidence', 0),
                "name_match": identity_data.get('name_match', False),
                "name_similarity": identity_data.get('name_similarity', 0),
                "extracted_name": identity_data.get('extracted_name', ''),
                "expected_name": identity_data.get('expected_name', ''),
                "face_verified": identity_data.get('face_verified', False),
                "face_confidence": identity_data.get('face_confidence', 0)
            },
            "requires_human_review": True,
            "failure_reason": self._get_failure_reason(identity_data)
        }
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(endpoint, json=payload) as response:
                    if response.status == 200:
                        logger.info(f"✅ Identity failure webhook sent for user {user_id}")
                        return True
                    else:
                        logger.error(f"❌ Webhook failed with status {response.status}")
                        return False
        except asyncio.TimeoutError:
            logger.error(f"⏱️ Webhook timeout for user {user_id}")
            return False
        except Exception as e:
            logger.error(f"❌ Webhook error for user {user_id}: {str(e)}")
            return False
    
    def _get_failure_reason(self, identity_data: Dict[str, Any]) -> str:
        """Determine specific failure reason from identity data"""
        name_match = identity_data.get('name_match', False)
        face_verified = identity_data.get('face_verified', False)
        
        if not name_match and not face_verified:
            return "Both name and face verification failed"
        elif not name_match:
            return f"Name mismatch: Expected '{identity_data.get('expected_name', '')}', Extracted '{identity_data.get('extracted_name', '')}'"
        elif not face_verified:
            return f"Face verification failed (confidence: {identity_data.get('face_confidence', 0):.1f}%)"
        else:
            return "Identity verification confidence below threshold"


# Global webhook client instance
_webhook_client = None


def get_webhook_client() -> WebhookClient:
    """Get or create global webhook client instance"""
    global _webhook_client
    if _webhook_client is None:
        _webhook_client = WebhookClient()
    return _webhook_client

