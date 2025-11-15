from sqlalchemy import Column, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import enum


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PENDING = "pending"


class BillingPeriod(str, enum.Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class Platform(str, enum.Enum):
    GOOGLE_PLAY = "google_play"
    APPLE_STORE = "apple_store"


class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    plan_tier = Column(String, nullable=False, index=True)  # 'free', 'pro', 'business'
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.PENDING, index=True)
    billing_period = Column(Enum(BillingPeriod), nullable=True)  # null for free tier
    platform = Column(Enum(Platform), nullable=True)  # null for free tier
    purchase_token = Column(String, nullable=True)  # Google Play purchase token
    receipt_data = Column(String, nullable=True)  # Apple receipt data or additional metadata
    start_date = Column(DateTime, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)  # null for free tier or until cancelled
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")

