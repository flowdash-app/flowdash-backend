"""
Refactored Firebase service with dependency injection for better testability
"""

from typing import Protocol, Optional
import firebase_admin
from firebase_admin import credentials, auth, firestore
from app.core.config import settings
import logging
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


class FirebaseAuthProvider(Protocol):
    """Protocol for Firebase authentication operations"""
    
    def verify_id_token(self, token: str) -> dict:
        """Verify Firebase ID token"""
        ...


class FirebaseFirestoreProvider(Protocol):
    """Protocol for Firestore operations"""
    
    def client(self):
        """Get Firestore client"""
        ...


class FirebaseService:
    """Firebase service with dependency injection support"""
    
    def __init__(
        self,
        auth_provider: Optional[FirebaseAuthProvider] = None,
        firestore_provider: Optional[FirebaseFirestoreProvider] = None
    ):
        self.auth_provider = auth_provider or auth
        self.firestore_provider = firestore_provider or firestore
        self.logger = logging.getLogger(__name__)
    
    def verify_token(self, token: str) -> dict:
        """Verify Firebase JWT token and return decoded token"""
        self.logger.info("verify_token: Entry")
        
        try:
            decoded_token = self.auth_provider.verify_id_token(token)
            self.logger.info(f"verify_token: Success - {decoded_token.get('uid')}")
            return decoded_token
        except Exception as e:
            self.logger.error(f"verify_token: Failure - {e}")
            raise
    
    def get_firestore_client(self):
        """Get Firestore client instance"""
        return self.firestore_provider.client()


# Global Firebase service instance
_firebase_service: Optional[FirebaseService] = None


def init_firebase():
    """Initialize Firebase Admin SDK"""
    logger.info("init_firebase: Entry")
    
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.firebase_credentials_path)
            firebase_admin.initialize_app(cred, {
                'projectId': settings.firebase_project_id,
            })
            logger.info("init_firebase: Success")
        else:
            logger.info("init_firebase: Already initialized")
    except Exception as e:
        logger.error(f"init_firebase: Failure - {e}")
        raise


def get_firebase_service() -> FirebaseService:
    """Get Firebase service instance (singleton)"""
    global _firebase_service
    if _firebase_service is None:
        _firebase_service = FirebaseService()
    return _firebase_service


def set_firebase_service(service: FirebaseService):
    """Set Firebase service instance (for testing)"""
    global _firebase_service
    _firebase_service = service


def verify_firebase_token(token: str) -> dict:
    """
    Verify Firebase JWT token and return decoded token.
    
    This is a backward-compatible wrapper that uses the FirebaseService.
    """
    service = get_firebase_service()
    return service.verify_token(token)


def get_firestore_client():
    """Get Firestore client instance (backward compatible)"""
    service = get_firebase_service()
    return service.get_firestore_client()


def get_fcm_access_token() -> str:
    """Get OAuth2 access token for FCM using Firebase Admin credentials"""
    logger.info("get_fcm_access_token: Entry")
    
    try:
        # Create service account credentials from Firebase credentials file
        creds = service_account.Credentials.from_service_account_file(
            settings.firebase_credentials_path,
            scopes=['https://www.googleapis.com/auth/firebase.messaging']
        )
        
        # Refresh the credentials to get an access token
        creds.refresh(Request())
        
        token = creds.token
        logger.info("get_fcm_access_token: Success")
        return token
    except Exception as e:
        logger.error(f"get_fcm_access_token: Failure - {e}")
        raise
