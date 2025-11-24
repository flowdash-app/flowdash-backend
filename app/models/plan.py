from sqlalchemy import Column, String, DateTime, Boolean, Numeric, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class Plan(Base):
    __tablename__ = "plans"
    
    tier = Column(String, primary_key=True)  # 'free', 'pro'
    name = Column(String, nullable=False)
    price_monthly = Column(Numeric(10, 2), nullable=False)
    price_yearly = Column(Numeric(10, 2), nullable=False)
    limits = Column(JSON, nullable=False)  # Store PlanLimits as JSON
    features = Column(JSON, nullable=False)  # Store as array
    active = Column(Boolean, default=True, nullable=False)
    recommended = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

