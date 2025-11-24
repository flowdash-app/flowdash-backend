import json
import logging
import uuid
from datetime import datetime, timedelta

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.subscription import (BillingPeriod, Platform, Subscription,
                                     SubscriptionStatus)
from app.models.subscription_history import SubscriptionHistory
from app.models.user import User
from app.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)


class PlanLimits(BaseModel):
    """Pydantic model for plan limits"""
    toggles_per_day: int
    refreshes_per_day: int
    error_views_per_day: int
    triggers: int
    max_instances: int
    push_notifications: bool
    cache_ttl_minutes: int = 10


class PlanResponse(BaseModel):
    """Pydantic model for plan API response"""
    tier: str
    name: str
    price_monthly: float
    price_yearly: float
    limits: PlanLimits
    features: list[str]
    recommended: bool = False

    class Config:
        from_attributes = True


class PlanConfiguration:
    """Legacy plan configuration - kept for backward compatibility during migration"""

    @classmethod
    def get_plan(cls, db: Session, plan_tier: str) -> dict:
        """Get plan configuration from database"""
        plan = db.query(Plan).filter(Plan.tier == plan_tier.lower()).first()
        if not plan:
            # Fallback to free if not found
            plan = db.query(Plan).filter(Plan.tier == 'free').first()
            if not plan:
                raise ValueError(f"Plan not found: {plan_tier}")

        limits = plan.limits
        return {
            'name': plan.name,
            'price_monthly': float(plan.price_monthly),
            'price_yearly': float(plan.price_yearly),
            'toggles_per_day': limits.get('toggles_per_day', 0),
            'refreshes_per_day': limits.get('refreshes_per_day', 5),
            'error_views_per_day': limits.get('error_views_per_day', 3),
            'triggers': limits.get('triggers', 1),
            'max_instances': limits.get('max_instances', 1),
            'push_notifications': limits.get('push_notifications', False),
            'cache_ttl_minutes': limits.get('cache_ttl_minutes', 10),
            'features': plan.features
        }

    @classmethod
    def get_limit(cls, db: Session, plan_tier: str, limit_type: str) -> int:
        """Get specific limit for a plan from database (-1 = unlimited)"""
        plan = db.query(Plan).filter(Plan.tier == plan_tier.lower()).first()
        if not plan:
            # Fallback to free if not found
            plan = db.query(Plan).filter(Plan.tier == 'free').first()
            if not plan:
                return 0

        limits = plan.limits
        # Map limit_type to limits dict key
        limit_map = {
            'toggles_per_day': 'toggles_per_day',
            'refreshes_per_day': 'refreshes_per_day',
            'error_views_per_day': 'error_views_per_day',
            'triggers': 'triggers',
            'max_instances': 'max_instances',
        }
        return limits.get(limit_map.get(limit_type, limit_type), 0)


class SubscriptionService:
    def __init__(self):
        self.analytics = AnalyticsService()
        self.logger = logging.getLogger(__name__)

    def get_all_plans(self, db: Session) -> list[dict]:
        """Get all available subscription plans from database"""
        self.logger.info("get_all_plans: Entry")

        try:
            # Seed plans if table is empty
            self._seed_plans_if_empty(db)

            # Query active plans from database
            plans_db = db.query(Plan).filter(
                Plan.active == True).order_by(Plan.price_monthly).all()

            # Convert to response format (exclude limits - they're returned separately in quota status)
            plans = []
            for plan in plans_db:
                # Return plan without limits to match mobile app Plan model
                plan_dict = {
                    'tier': plan.tier,
                    'name': plan.name,
                    'price_monthly': float(plan.price_monthly),
                    'price_yearly': float(plan.price_yearly),
                    'features': plan.features,
                    'recommended': plan.recommended
                }
                plans.append(plan_dict)

            self.logger.info(f"get_all_plans: Success - {len(plans)} plans")
            return plans
        except Exception as e:
            self.analytics.log_failure(
                action='get_all_plans',
                error=str(e)
            )
            self.logger.error(f"get_all_plans: Failure - {e}")
            raise

    def _seed_plans_if_empty(self, db: Session):
        """Seed plans table if empty (for initial setup or if migration didn't run)"""
        try:
            plan_count = db.query(Plan).count()
            if plan_count == 0:
                self.logger.info(
                    "_seed_plans_if_empty: Plans table is empty, seeding plans")

                # Free plan
                free_plan = Plan(
                    tier='free',
                    name='Free',
                    price_monthly=0.00,
                    price_yearly=0.00,
                    limits={
                        'toggles_per_day': 0,
                        'refreshes_per_day': 5,
                        'error_views_per_day': 3,
                        'triggers': 1,
                        'max_instances': 1,
                        'push_notifications': False,
                        'cache_ttl_minutes': 30
                    },
                    features=[
                        'Read-only monitoring',
                        '5 list refreshes per day',
                        '3 detailed error views per day',
                        '1 simple mobile trigger',
                        '1 n8n instance',
                        '30-minute data cache',
                    ],
                    active=True,
                    recommended=False
                )
                db.add(free_plan)

                # Pro plan
                pro_plan = Plan(
                    tier='pro',
                    name='Pro',
                    price_monthly=19.99,
                    price_yearly=199.99,
                    limits={
                        'toggles_per_day': 100,
                        'refreshes_per_day': 200,
                        'error_views_per_day': -1,
                        'triggers': 10,
                        'max_instances': 5,
                        'push_notifications': True,
                        'cache_ttl_minutes': 3
                    },
                    features=[
                        'Instant push notifications',
                        '100 workflow toggles per day',
                        '200 list refreshes per day',
                        'Unlimited detailed error views',
                        '10 custom triggers with forms',
                        'Up to 5 n8n instances',
                    ],
                    active=True,
                    recommended=True
                )
                db.add(pro_plan)

                db.commit()
                self.logger.info(
                    "_seed_plans_if_empty: Success - seeded free and pro plans")
        except Exception as e:
            db.rollback()
            self.logger.error(f"_seed_plans_if_empty: Failure - {e}")
            # Don't raise - allow API to continue even if seeding fails

    def get_current_subscription(self, db: Session, user_id: str) -> dict:
        """Get user's current subscription"""
        self.logger.info(f"get_current_subscription: Entry - user: {user_id}")

        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Get active subscription
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            ).order_by(Subscription.created_at.desc()).first()

            # Testers get unlimited access (handled in quota/rate limit checks)
            # Use user's actual plan tier for display
            effective_plan = user.plan_tier
            plan_config = PlanConfiguration.get_plan(db, effective_plan)

            result = {
                'user_id': user_id,
                'plan_tier': effective_plan,
                'plan_name': plan_config['name'] + (' (Tester)' if user.is_tester else ''),
                'is_tester': user.is_tester,
                'status': subscription.status.value if subscription else 'active',
                'billing_period': subscription.billing_period.value if subscription and subscription.billing_period else None,
                'platform': subscription.platform.value if subscription and subscription.platform else None,
                'start_date': subscription.start_date.isoformat() if subscription else None,
                'end_date': subscription.end_date.isoformat() if subscription and subscription.end_date else None,
                'limits': {
                    'toggles_per_day': plan_config['toggles_per_day'],
                    'refreshes_per_day': plan_config['refreshes_per_day'],
                    'error_views_per_day': plan_config['error_views_per_day'],
                    'triggers': plan_config['triggers'],
                    'max_instances': plan_config['max_instances'],
                    'push_notifications': plan_config['push_notifications']
                }
            }

            self.analytics.log_success(
                action='get_current_subscription',
                user_id=user_id,
                parameters={'plan_tier': user.plan_tier}
            )
            self.logger.info(
                f"get_current_subscription: Success - user: {user_id}, tier: {user.plan_tier}")
            return result
        except Exception as e:
            self.analytics.log_failure(
                action='get_current_subscription',
                error=str(e),
                user_id=user_id
            )
            self.logger.error(f"get_current_subscription: Failure - {e}")
            raise

    def verify_purchase(
        self,
        db: Session,
        user_id: str,
        plan_tier: str,
        billing_period: str,
        platform: str,
        purchase_token: str,
        receipt_data: str = None
    ) -> Subscription:
        """Verify and create subscription from purchase"""
        self.logger.info(
            f"verify_purchase: Entry - user: {user_id}, tier: {plan_tier}, platform: {platform}")

        try:
            # Validate plan tier exists in database
            plan = db.query(Plan).filter(
                Plan.tier == plan_tier.lower()).first()
            if not plan:
                raise ValueError(f"Invalid plan tier: {plan_tier}")

            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            # Store old plan for history
            old_plan = user.plan_tier

            # Cancel any existing active subscriptions
            existing_subs = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            ).all()

            for sub in existing_subs:
                sub.status = SubscriptionStatus.CANCELLED
                sub.updated_at = datetime.utcnow()

            # Calculate end date based on billing period
            start_date = datetime.utcnow()
            if billing_period == 'monthly':
                end_date = start_date + timedelta(days=30)
            elif billing_period == 'yearly':
                end_date = start_date + timedelta(days=365)
            else:
                raise ValueError(f"Invalid billing period: {billing_period}")

            # Create new subscription
            subscription = Subscription(
                id=str(uuid.uuid4()),
                user_id=user_id,
                plan_tier=plan_tier,
                status=SubscriptionStatus.ACTIVE,
                billing_period=BillingPeriod[billing_period.upper()],
                platform=Platform[platform.upper()],
                purchase_token=purchase_token,
                receipt_data=receipt_data,
                start_date=start_date,
                end_date=end_date
            )
            db.add(subscription)

            # Update user plan tier
            user.plan_tier = plan_tier
            user.updated_at = datetime.utcnow()

            # Create history entry
            history = SubscriptionHistory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                subscription_id=subscription.id,
                action='created' if old_plan == 'free' else 'upgraded',
                from_plan=old_plan,
                to_plan=plan_tier,
                details=json.dumps({
                    'platform': platform,
                    'billing_period': billing_period,
                    'purchase_token': purchase_token[:20] + '...' if purchase_token else None
                })
            )
            db.add(history)

            db.commit()
            db.refresh(subscription)

            self.analytics.log_success(
                action='verify_purchase',
                user_id=user_id,
                parameters={
                    'plan_tier': plan_tier,
                    'billing_period': billing_period,
                    'platform': platform,
                    'from_plan': old_plan
                }
            )
            self.logger.info(
                f"verify_purchase: Success - user: {user_id}, subscription: {subscription.id}")
            return subscription
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='verify_purchase',
                error=str(e),
                user_id=user_id,
                parameters={
                    'plan_tier': plan_tier,
                    'platform': platform
                }
            )
            self.logger.error(f"verify_purchase: Failure - {e}")
            raise

    def cancel_subscription(self, db: Session, user_id: str) -> Subscription:
        """Cancel user's active subscription"""
        self.logger.info(f"cancel_subscription: Entry - user: {user_id}")

        try:
            # Get active subscription
            subscription = db.query(Subscription).filter(
                Subscription.user_id == user_id,
                Subscription.status == SubscriptionStatus.ACTIVE
            ).order_by(Subscription.created_at.desc()).first()

            if not subscription:
                raise ValueError("No active subscription found")

            # Update subscription status
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.updated_at = datetime.utcnow()
            # Keep end_date - subscription remains active until end date

            # Create history entry
            history = SubscriptionHistory(
                id=str(uuid.uuid4()),
                user_id=user_id,
                subscription_id=subscription.id,
                action='cancelled',
                from_plan=subscription.plan_tier,
                to_plan='free',  # Will revert to free after end_date
                details=json.dumps({
                    'cancelled_at': datetime.utcnow().isoformat(),
                    'end_date': subscription.end_date.isoformat() if subscription.end_date else None
                })
            )
            db.add(history)

            db.commit()
            db.refresh(subscription)

            self.analytics.log_success(
                action='cancel_subscription',
                user_id=user_id,
                parameters={
                    'subscription_id': subscription.id,
                    'plan_tier': subscription.plan_tier
                }
            )
            self.logger.info(
                f"cancel_subscription: Success - user: {user_id}, subscription: {subscription.id}")
            return subscription
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='cancel_subscription',
                error=str(e),
                user_id=user_id
            )
            self.logger.error(f"cancel_subscription: Failure - {e}")
            raise

    def get_subscription_history(self, db: Session, user_id: str) -> list[dict]:
        """Get user's subscription history"""
        self.logger.info(f"get_subscription_history: Entry - user: {user_id}")

        try:
            history = db.query(SubscriptionHistory).filter(
                SubscriptionHistory.user_id == user_id
            ).order_by(SubscriptionHistory.created_at.desc()).all()

            result = []
            for entry in history:
                result.append({
                    'id': entry.id,
                    'action': entry.action,
                    'from_plan': entry.from_plan,
                    'to_plan': entry.to_plan,
                    'created_at': entry.created_at.isoformat(),
                    'details': json.loads(entry.details) if entry.details else None
                })

            self.analytics.log_success(
                action='get_subscription_history',
                user_id=user_id,
                parameters={'count': len(result)}
            )
            self.logger.info(
                f"get_subscription_history: Success - user: {user_id}, count: {len(result)}")
            return result
        except Exception as e:
            self.analytics.log_failure(
                action='get_subscription_history',
                error=str(e),
                user_id=user_id
            )
            self.logger.error(f"get_subscription_history: Failure - {e}")
            raise

    def check_expired_subscriptions(self, db: Session) -> int:
        """Check and expire subscriptions that have passed their end_date"""
        self.logger.info("check_expired_subscriptions: Entry")

        try:
            now = datetime.utcnow()

            # Find active subscriptions that have expired
            expired_subs = db.query(Subscription).filter(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.end_date < now
            ).all()

            count = 0
            for subscription in expired_subs:
                subscription.status = SubscriptionStatus.EXPIRED
                subscription.updated_at = now

                # Update user plan tier to free
                user = db.query(User).filter(
                    User.id == subscription.user_id).first()
                if user:
                    user.plan_tier = 'free'
                    user.updated_at = now

                # Create history entry
                history = SubscriptionHistory(
                    id=str(uuid.uuid4()),
                    user_id=subscription.user_id,
                    subscription_id=subscription.id,
                    action='expired',
                    from_plan=subscription.plan_tier,
                    to_plan='free',
                    details=json.dumps({
                        'expired_at': now.isoformat(),
                        'end_date': subscription.end_date.isoformat()
                    })
                )
                db.add(history)
                count += 1

            db.commit()

            self.analytics.log_success(
                action='check_expired_subscriptions',
                parameters={'expired_count': count}
            )
            self.logger.info(
                f"check_expired_subscriptions: Success - expired: {count}")
            return count
        except Exception as e:
            db.rollback()
            self.analytics.log_failure(
                action='check_expired_subscriptions',
                error=str(e)
            )
            self.logger.error(f"check_expired_subscriptions: Failure - {e}")
            raise
