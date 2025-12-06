"""
Integration tests for database operations
"""

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models.n8n_instance import N8NInstance
from app.models.quota import Quota
from app.models.user import User


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database operations"""

    def test_create_user(self, db_session: Session):
        """Test creating a user in the database"""
        # Skip if no database connection
        if db_session is None:
            pytest.skip("Database not available")

        # Create user
        user = User(
            id="test_user_db_123",
            email="dbtest@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
            plan_tier="free",
            is_tester=False
        )

        db_session.add(user)
        db_session.commit()

        # Verify
        retrieved = db_session.query(User).filter(User.id == "test_user_db_123").first()
        assert retrieved is not None
        assert retrieved.email == "dbtest@example.com"
        assert retrieved.plan_tier == "free"

    def test_create_instance_with_user(self, db_session: Session):
        """Test creating an n8n instance linked to a user"""
        if db_session is None:
            pytest.skip("Database not available")

        # Create user first
        user = User(
            id="test_user_inst_123",
            email="insttest@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
            plan_tier="pro",
            is_tester=False
        )
        db_session.add(user)
        db_session.commit()

        # Create instance
        instance = N8NInstance(
            id="test_instance_123",
            user_id=user.id,
            name="Test Instance",
            url="https://test.n8n.cloud",
            api_key_encrypted="encrypted_key_here",
            enabled=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(instance)
        db_session.commit()

        # Verify
        retrieved = db_session.query(N8NInstance).filter(
            N8NInstance.id == "test_instance_123"
        ).first()
        assert retrieved is not None
        assert retrieved.user_id == user.id
        assert retrieved.name == "Test Instance"

    def test_query_user_instances(self, db_session: Session):
        """Test querying all instances for a user"""
        if db_session is None:
            pytest.skip("Database not available")

        # Create user
        user = User(
            id="test_user_multi_123",
            email="multitest@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
            plan_tier="pro",
            is_tester=False
        )
        db_session.add(user)
        db_session.commit()

        # Create multiple instances
        for i in range(3):
            instance = N8NInstance(
                id=f"test_instance_multi_{i}",
                user_id=user.id,
                name=f"Test Instance {i}",
                url=f"https://test{i}.n8n.cloud",
                api_key_encrypted=f"encrypted_key_{i}",
                enabled=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db_session.add(instance)
        db_session.commit()

        # Query instances
        instances = db_session.query(N8NInstance).filter(
            N8NInstance.user_id == user.id
        ).all()

        # Verify
        assert len(instances) == 3
        assert all(inst.user_id == user.id for inst in instances)

    def test_create_quota(self, db_session: Session):
        """Test creating a quota record"""
        if db_session is None:
            pytest.skip("Database not available")

        # Create user
        user = User(
            id="test_user_quota_123",
            email="quotatest@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
            plan_tier="free",
            is_tester=False
        )
        db_session.add(user)
        db_session.commit()

        # Create quota
        quota = Quota(
            id="test_quota_123",
            user_id=user.id,
            quota_type="toggles",
            count=5,
            quota_date=datetime.utcnow().date(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(quota)
        db_session.commit()

        # Verify
        retrieved = db_session.query(Quota).filter(
            Quota.user_id == user.id,
            Quota.quota_type == "toggles"
        ).first()
        assert retrieved is not None
        assert retrieved.count == 5
