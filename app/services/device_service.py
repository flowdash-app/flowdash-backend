from app.core.firebase import get_firestore_client
from firebase_admin import firestore
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class DeviceService:
    def __init__(self):
        self.db = get_firestore_client()
        self.logger = logging.getLogger(__name__)
    
    def register_device(
        self,
        user_id: str,
        device_id: str,
        fcm_token: str,
        platform: str
    ):
        """Register or update device token for user
        
        Args:
            user_id: Firebase UID
            device_id: Unique device identifier
            fcm_token: FCM push notification token
            platform: 'ios' or 'android'
        """
        self.logger.info(f"register_device: Entry - user: {user_id}, device: {device_id}, platform: {platform}")
        
        try:
            # Reference to device document
            device_ref = self.db.collection('users').document(user_id).collection('devices').document(device_id)
            
            # Get current timestamp
            now = firestore.SERVER_TIMESTAMP
            
            # Check if device exists
            device_doc = device_ref.get()
            
            if device_doc.exists:
                # Update existing device - only update fcm_token and last_used_at
                device_ref.update({
                    'fcm_token': fcm_token,
                    'last_used_at': now,
                })
                self.logger.info(f"register_device: Success (updated) - user: {user_id}, device: {device_id}")
            else:
                # Create new device document
                device_ref.set({
                    'fcm_token': fcm_token,
                    'platform': platform,
                    'created_at': now,
                    'last_used_at': now,
                })
                self.logger.info(f"register_device: Success (created) - user: {user_id}, device: {device_id}")
            
        except Exception as e:
            self.logger.error(f"register_device: Failure - {e}")
            raise
    
    def delete_device(self, user_id: str, device_id: str):
        """Delete device token for user (on logout)
        
        Args:
            user_id: Firebase UID
            device_id: Unique device identifier
        """
        self.logger.info(f"delete_device: Entry - user: {user_id}, device: {device_id}")
        
        try:
            device_ref = self.db.collection('users').document(user_id).collection('devices').document(device_id)
            device_ref.delete()
            self.logger.info(f"delete_device: Success - user: {user_id}, device: {device_id}")
        except Exception as e:
            self.logger.error(f"delete_device: Failure - {e}")
            raise
    
    def get_user_devices(self, user_id: str) -> list:
        """Get all devices for a user
        
        Args:
            user_id: Firebase UID
            
        Returns:
            List of device dictionaries with id, fcm_token, platform, created_at, last_used_at
        """
        self.logger.info(f"get_user_devices: Entry - user: {user_id}")
        
        try:
            devices_ref = self.db.collection('users').document(user_id).collection('devices')
            devices_docs = devices_ref.stream()
            
            devices = []
            for doc in devices_docs:
                device_data = doc.to_dict()
                device_data['id'] = doc.id
                devices.append(device_data)
            
            self.logger.info(f"get_user_devices: Success - user: {user_id}, count: {len(devices)}")
            return devices
        except Exception as e:
            self.logger.error(f"get_user_devices: Failure - {e}")
            raise
    
    def cleanup_stale_tokens(self, days: int = 30):
        """Remove device tokens not used in specified days
        
        NOTE: This should be called by a scheduled job (cron/Cloud Scheduler)
        to run daily and clean up inactive device tokens.
        
        Args:
            days: Number of days of inactivity before cleanup (default: 30)
        """
        self.logger.info(f"cleanup_stale_tokens: Entry - days: {days}")
        
        try:
            # Calculate cutoff timestamp
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Query all users
            users_ref = self.db.collection('users')
            users_docs = users_ref.stream()
            
            deleted_count = 0
            
            for user_doc in users_docs:
                user_id = user_doc.id
                devices_ref = user_doc.reference.collection('devices')
                devices_docs = devices_ref.stream()
                
                for device_doc in devices_docs:
                    device_data = device_doc.to_dict()
                    last_used_at = device_data.get('last_used_at')
                    
                    # Convert Firestore timestamp to datetime if needed
                    if last_used_at and hasattr(last_used_at, 'timestamp'):
                        last_used_dt = datetime.fromtimestamp(last_used_at.timestamp())
                    elif isinstance(last_used_at, datetime):
                        last_used_dt = last_used_at
                    else:
                        # Skip if no valid timestamp
                        continue
                    
                    # Delete if older than cutoff
                    if last_used_dt < cutoff:
                        device_doc.reference.delete()
                        deleted_count += 1
                        self.logger.info(
                            f"cleanup_stale_tokens: Deleted stale token - "
                            f"user: {user_id}, device: {device_doc.id}, "
                            f"last_used: {last_used_dt}"
                        )
            
            self.logger.info(f"cleanup_stale_tokens: Success - deleted {deleted_count} stale tokens")
            return deleted_count
        except Exception as e:
            self.logger.error(f"cleanup_stale_tokens: Failure - {e}")
            raise

