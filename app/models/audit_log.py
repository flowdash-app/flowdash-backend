from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    action = Column(String, nullable=False, index=True)  # 'toggle_workflow', 'view_error', etc.
    resource_type = Column(String, nullable=False)  # 'workflow', 'instance', etc.
    resource_id = Column(String, nullable=True)
    metadata = Column(Text)  # JSON string for additional data
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User")

