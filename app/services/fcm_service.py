import httpx
from app.core.config import settings
from app.core.firebase import get_firestore_client, get_fcm_access_token
from firebase_admin import firestore
import logging

logger = logging.getLogger(__name__)


class FCMService:
    def __init__(self):
        self.firebase_project_id = settings.firebase_project_id
        self.fcm_url = f"https://fcm.googleapis.com/v1/projects/{self.firebase_project_id}/messages:send"
        self.db = get_firestore_client()
        self.logger = logging.getLogger(__name__)
    
    def get_fcm_token(self, user_id: str) -> str:
        """Get FCM token for user from Firestore"""
        self.logger.info(f"get_fcm_token: Entry - user: {user_id}")
        
        try:
            # Assuming FCM tokens are stored in a 'fcm_tokens' collection
            # with document ID = user_id and field 'token'
            doc_ref = self.db.collection('fcm_tokens').document(user_id)
            doc = doc_ref.get()
            
            if doc.exists:
                token = doc.to_dict().get('token')
                self.logger.info(f"get_fcm_token: Success - user: {user_id}")
                return token
            else:
                self.logger.warning(f"get_fcm_token: No token found - user: {user_id}")
                return None
        except Exception as e:
            self.logger.error(f"get_fcm_token: Failure - {e}")
            return None
    
    async def send_error_notification(
        self,
        user_id: str,
        workflow_id: str,
        execution_id: str,
        error_message: str
    ):
        """Send FCM push notification for n8n error"""
        self.logger.info(f"send_error_notification: Entry - user: {user_id}, execution: {execution_id}")
        
        try:
            # Get FCM token for user
            fcm_token = self.get_fcm_token(user_id)
            
            if not fcm_token:
                self.logger.warning(f"send_error_notification: No FCM token for user: {user_id}")
                return
            
            # Prepare FCM message
            message = {
                "message": {
                    "token": fcm_token,
                    "notification": {
                        "title": "n8n Workflow Error",
                        "body": f"Workflow {workflow_id} failed: {error_message[:100]}"
                    },
                    "data": {
                        "workflow_id": workflow_id,
                        "execution_id": execution_id,
                        "error_message": error_message,
                        "type": "workflow_error"
                    },
                    "android": {
                        "priority": "high"
                    },
                    "apns": {
                        "headers": {
                            "apns-priority": "10"
                        }
                    }
                }
            }
            
            # Send notification using FCM HTTP v1 API with OAuth2 token
            access_token = get_fcm_access_token()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.fcm_url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json=message,
                    timeout=30.0
                )
                response.raise_for_status()
            
            self.logger.info(f"send_error_notification: Success - user: {user_id}, execution: {execution_id}")
        except Exception as e:
            self.logger.error(f"send_error_notification: Failure - {e}")
            # Don't raise - notification failures shouldn't break webhook processing
            pass

