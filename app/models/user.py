from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, index=True)  # Firebase UID
    email = Column(String, unique=True, index=True, nullable=False)
    plan_tier = Column(String, nullable=False, default='free', index=True)  # 'free', 'pro', 'business'
    is_tester = Column(Boolean, default=False, nullable=False)  # Testers get pro-level access without subscription
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    n8n_instances = relationship("N8NInstance", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")

