from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class SubscriptionHistory(Base):
    __tablename__ = "subscription_history"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    subscription_id = Column(String, ForeignKey("subscriptions.id"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)  # 'created', 'upgraded', 'cancelled', 'renewed', 'expired'
    from_plan = Column(String, nullable=True)
    to_plan = Column(String, nullable=True)
    details = Column(Text, nullable=True)  # JSON for additional details (renamed from 'metadata' to avoid SQLAlchemy conflict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User")
    subscription = relationship("Subscription")

