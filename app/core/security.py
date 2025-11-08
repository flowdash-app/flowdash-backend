from cryptography.fernet import Fernet
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_cipher():
    """Get Fernet cipher instance for encryption/decryption"""
    key = settings.encryption_key.encode()
    return Fernet(key)


def encrypt_api_key(api_key: str) -> str:
    """Encrypt n8n API key before storing in database"""
    logger.info("encrypt_api_key: Entry")
    
    try:
        cipher = get_cipher()
        encrypted = cipher.encrypt(api_key.encode())
        logger.info("encrypt_api_key: Success")
        return encrypted.decode()
    except Exception as e:
        logger.error(f"encrypt_api_key: Failure - {e}")
        raise


def decrypt_api_key(encrypted_key: str) -> str:
    """Decrypt n8n API key from database"""
    logger.info("decrypt_api_key: Entry")
    
    try:
        cipher = get_cipher()
        decrypted = cipher.decrypt(encrypted_key.encode())
        logger.info("decrypt_api_key: Success")
        return decrypted.decode()
    except Exception as e:
        logger.error(f"decrypt_api_key: Failure - {e}")
        raise

