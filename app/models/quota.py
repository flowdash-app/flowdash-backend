from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime, date


class Quota(Base):
    __tablename__ = "quotas"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    quota_type = Column(String, nullable=False, index=True)  # 'toggles', 'refreshes', 'error_views', etc.
    count = Column(Integer, default=0)
    quota_date = Column(Date, default=date.today, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User")

