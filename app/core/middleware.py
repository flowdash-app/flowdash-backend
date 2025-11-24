from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.firebase import verify_firebase_token
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency to get current authenticated user from Firebase token.
    Protects routes that require authentication.
    """
    logger.info("get_current_user: Entry")
    
    try:
        token = credentials.credentials
        decoded_token = verify_firebase_token(token)
        user_id = decoded_token.get('uid')
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        logger.info(f"get_current_user: Success - {user_id}")
        user_dict = {
            'uid': user_id,
            'email': decoded_token.get('email'),
            'token': decoded_token
        }
        # Store user_id in request state for rate limiting (if request is available)
        # This will be set by FastAPI's dependency injection
        return user_dict
    except Exception as e:
        logger.error(f"get_current_user: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

