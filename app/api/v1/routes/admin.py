from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.middleware import get_current_user
from app.models.user import User
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Configuration - adjust as needed
MAX_TESTERS = 100
ADMIN_EMAILS = []  # Add admin emails here, or implement proper admin role system


class SetTesterRequest(BaseModel):
    user_email: str
    is_tester: bool


def is_admin(current_user: dict) -> bool:
    """Check if user is admin (basic check - enhance with proper role system)"""
    # TODO: Implement proper admin role system
    # For now, you can manually add admin emails to ADMIN_EMAILS list
    # Or use Firebase custom claims for admin role
    return current_user.get('email') in ADMIN_EMAILS


@router.post("/set-tester")
async def set_tester_status(
    request: SetTesterRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Set or remove tester status for a user.
    Only admins can use this endpoint.
    """
    logger.info(f"set_tester_status: Entry - target: {request.user_email}, tester: {request.is_tester}")
    
    # Check admin permission
    if not is_admin(current_user):
        logger.warning(f"set_tester_status: Unauthorized - user: {current_user['email']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        # Get target user
        user = db.query(User).filter(User.email == request.user_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {request.user_email}"
            )
        
        # If granting tester status, check limit
        if request.is_tester and not user.is_tester:
            tester_count = db.query(User).filter(User.is_tester == True).count()
            if tester_count >= MAX_TESTERS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tester limit reached ({MAX_TESTERS})"
                )
        
        # Update tester status
        user.is_tester = request.is_tester
        db.commit()
        db.refresh(user)
        
        logger.info(
            f"set_tester_status: Success - user: {user.email}, "
            f"is_tester: {user.is_tester}"
        )
        
        return {
            "message": f"Tester status updated for {user.email}",
            "user_email": user.email,
            "is_tester": user.is_tester,
            "plan_tier": user.plan_tier
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"set_tester_status: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/testers")
async def list_testers(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List all users with tester status.
    Only admins can use this endpoint.
    """
    logger.info("list_testers: Entry")
    
    # Check admin permission
    if not is_admin(current_user):
        logger.warning(f"list_testers: Unauthorized - user: {current_user['email']}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        testers = db.query(User).filter(User.is_tester == True).all()
        
        result = {
            "count": len(testers),
            "max_testers": MAX_TESTERS,
            "testers": [
                {
                    "email": user.email,
                    "id": user.id,
                    "plan_tier": user.plan_tier,
                    "created_at": user.created_at.isoformat(),
                }
                for user in testers
            ]
        }
        
        logger.info(f"list_testers: Success - count: {len(testers)}")
        return result
    
    except Exception as e:
        logger.error(f"list_testers: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

