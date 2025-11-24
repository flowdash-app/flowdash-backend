import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.middleware import get_current_user
from app.services.quota_service import QuotaService
from app.services.subscription_service import SubscriptionService

router = APIRouter()
logger = logging.getLogger(__name__)


def get_subscription_service() -> SubscriptionService:
    """Dependency to get subscription service instance"""
    return SubscriptionService()


def get_quota_service() -> QuotaService:
    """Dependency to get quota service instance"""
    return QuotaService()


class VerifyPurchaseRequest(BaseModel):
    plan_tier: str
    billing_period: str  # 'monthly' or 'yearly'
    platform: str  # 'google_play', 'apple_store', 'stripe', 'paypal', etc.
    purchase_token: Optional[str] = None  # For in-app purchases
    receipt_data: Optional[str] = None  # For in-app purchases
    # 'stripe', 'paypal', etc. for external payments
    payment_provider: Optional[str] = None
    payment_intent_id: Optional[str] = None  # Stripe payment intent ID
    # PayPal transaction ID or other provider transaction ID
    transaction_id: Optional[str] = None


@router.get("/plans")
async def get_plans(
    db: Session = Depends(get_db),
    subscription_service: SubscriptionService = Depends(
        get_subscription_service)
):
    """
    Get all available subscription plans.
    Public endpoint - no authentication required.
    """
    logger.info("get_plans: Entry")

    try:
        plans = subscription_service.get_all_plans(db)
        logger.info(f"get_plans: Success - {len(plans)} plans")
        return {"plans": plans}
    except Exception as e:
        logger.error(f"get_plans: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/current")
async def get_current_subscription(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(
        get_subscription_service)
):
    """
    Get current user's subscription details.
    Requires authentication.
    """
    user_id = current_user['uid']
    logger.info(f"get_current_subscription: Entry - user: {user_id}")

    try:
        subscription = subscription_service.get_current_subscription(
            db, user_id)
        logger.info(f"get_current_subscription: Success - user: {user_id}")
        return subscription
    except ValueError as e:
        logger.error(f"get_current_subscription: ValueError - {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"get_current_subscription: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/verify")
async def verify_purchase(
    request: VerifyPurchaseRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(
        get_subscription_service)
):
    """
    Verify and activate a subscription purchase.
    Called by mobile app after successful in-app purchase.
    Requires authentication.
    """
    user_id = current_user['uid']
    logger.info(
        f"verify_purchase: Entry - user: {user_id}, tier: {request.plan_tier}")

    try:
        # TODO: Add actual receipt verification with Google Play / Apple Store APIs
        # TODO: Add payment verification with Stripe / PayPal APIs for external payments
        # For now, we trust the client (this should be enhanced in production)

        # For external payments, use transaction_id as purchase_token
        purchase_token = request.purchase_token or request.transaction_id or request.payment_intent_id

        subscription = subscription_service.verify_purchase(
            db=db,
            user_id=user_id,
            plan_tier=request.plan_tier,
            billing_period=request.billing_period,
            platform=request.platform,
            purchase_token=purchase_token,
            receipt_data=request.receipt_data
        )

        logger.info(
            f"verify_purchase: Success - user: {user_id}, subscription: {subscription.id}")
        return {
            "subscription_id": subscription.id,
            "plan_tier": subscription.plan_tier,
            "status": subscription.status.value,
            "start_date": subscription.start_date.isoformat(),
            "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
            "message": "Subscription activated successfully"
        }
    except ValueError as e:
        logger.error(f"verify_purchase: ValueError - {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"verify_purchase: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/cancel")
async def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(
        get_subscription_service)
):
    """
    Cancel current subscription.
    Subscription remains active until end date.
    Requires authentication.
    """
    user_id = current_user['uid']
    logger.info(f"cancel_subscription: Entry - user: {user_id}")

    try:
        subscription = subscription_service.cancel_subscription(db, user_id)
        logger.info(
            f"cancel_subscription: Success - user: {user_id}, subscription: {subscription.id}")
        return {
            "subscription_id": subscription.id,
            "status": subscription.status.value,
            "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
            "message": "Subscription cancelled. Access will continue until end date."
        }
    except ValueError as e:
        logger.error(f"cancel_subscription: ValueError - {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"cancel_subscription: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/history")
async def get_subscription_history(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    subscription_service: SubscriptionService = Depends(
        get_subscription_service)
):
    """
    Get subscription history for current user.
    Requires authentication.
    """
    user_id = current_user['uid']
    logger.info(f"get_subscription_history: Entry - user: {user_id}")

    try:
        history = subscription_service.get_subscription_history(db, user_id)
        logger.info(
            f"get_subscription_history: Success - user: {user_id}, count: {len(history)}")
        return {"history": history}
    except Exception as e:
        logger.error(f"get_subscription_history: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/quota-status")
async def get_quota_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    quota_service: QuotaService = Depends(get_quota_service)
):
    """
    Get current quota usage status for all quota types.
    Requires authentication.
    """
    user_id = current_user['uid']
    logger.info(f"get_quota_status: Entry - user: {user_id}")

    try:
        quota_status = quota_service.get_quota_status(db, user_id)
        logger.info(f"get_quota_status: Success - user: {user_id}")
        return quota_status
    except ValueError as e:
        logger.error(f"get_quota_status: ValueError - {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"get_quota_status: Failure - {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
