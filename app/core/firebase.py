import firebase_admin
from firebase_admin import credentials, auth, firestore
from app.core.config import settings
import logging
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)


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


def verify_firebase_token(token: str) -> dict:
    """Verify Firebase JWT token and return decoded token"""
    logger.info("verify_firebase_token: Entry")
    
    try:
        decoded_token = auth.verify_id_token(token)
        logger.info(f"verify_firebase_token: Success - {decoded_token.get('uid')}")
        return decoded_token
    except Exception as e:
        logger.error(f"verify_firebase_token: Failure - {e}")
        raise


def get_firestore_client():
    """Get Firestore client instance"""
    return firestore.client()


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

