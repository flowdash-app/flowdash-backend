"""
Tests for Firebase integration with dependency injection
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from datetime import datetime, timedelta

from app.core.firebase_service import (
    FirebaseService,
    get_firebase_service,
    set_firebase_service,
    verify_firebase_token
)


@pytest.fixture
def mock_auth_provider():
    """Mock Firebase auth provider"""
    provider = MagicMock()
    provider.verify_id_token.return_value = {
        "uid": "test_user_123",
        "email": "test@example.com",
        "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp())
    }
    return provider


@pytest.fixture
def mock_firestore_provider():
    """Mock Firestore provider"""
    provider = MagicMock()
    mock_client = MagicMock()
    provider.client.return_value = mock_client
    return provider


class TestFirebaseServiceDependencyInjection:
    """Test Firebase service with dependency injection"""

    def test_firebase_service_with_mock_provider(self, mock_auth_provider):
        """Test FirebaseService can be instantiated with mock provider"""
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        token = "mock_token_123"
        result = service.verify_token(token)
        
        assert result["uid"] == "test_user_123"
        assert result["email"] == "test@example.com"
        mock_auth_provider.verify_id_token.assert_called_once_with(token)

    def test_firebase_service_token_verification(self, mock_auth_provider):
        """Test token verification through service"""
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        result = service.verify_token("test_token")
        
        assert "uid" in result
        assert "email" in result

    def test_firebase_service_raises_on_invalid_token(self, mock_auth_provider):
        """Test service raises exception for invalid token"""
        mock_auth_provider.verify_id_token.side_effect = Exception("Invalid token")
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        with pytest.raises(Exception) as exc_info:
            service.verify_token("invalid_token")
        
        assert "Invalid token" in str(exc_info.value)

    def test_firebase_service_with_firestore_provider(self, mock_firestore_provider):
        """Test FirebaseService with Firestore provider"""
        service = FirebaseService(firestore_provider=mock_firestore_provider)
        
        client = service.get_firestore_client()
        
        assert client is not None
        mock_firestore_provider.client.assert_called_once()


class TestFirebaseServiceSingleton:
    """Test Firebase service singleton pattern"""

    def test_get_firebase_service_returns_instance(self):
        """Test get_firebase_service returns a service instance"""
        service = get_firebase_service()
        
        assert service is not None
        assert isinstance(service, FirebaseService)

    def test_get_firebase_service_returns_same_instance(self):
        """Test get_firebase_service returns same instance"""
        service1 = get_firebase_service()
        service2 = get_firebase_service()
        
        assert service1 is service2

    def test_set_firebase_service_replaces_instance(self, mock_auth_provider):
        """Test set_firebase_service replaces the global instance"""
        mock_service = FirebaseService(auth_provider=mock_auth_provider)
        
        set_firebase_service(mock_service)
        service = get_firebase_service()
        
        assert service is mock_service


class TestBackwardCompatibility:
    """Test backward compatibility of Firebase functions"""

    def test_verify_firebase_token_wrapper(self, mock_auth_provider):
        """Test verify_firebase_token wrapper function"""
        mock_service = FirebaseService(auth_provider=mock_auth_provider)
        set_firebase_service(mock_service)
        
        result = verify_firebase_token("test_token")
        
        assert result["uid"] == "test_user_123"
        mock_auth_provider.verify_id_token.assert_called_once()


class TestFirebaseTokenValidation:
    """Test Firebase token validation scenarios"""

    def test_valid_token_structure(self, mock_auth_provider):
        """Test valid token returns expected structure"""
        mock_auth_provider.verify_id_token.return_value = {
            "uid": "user_123",
            "email": "user@example.com",
            "email_verified": True,
            "iat": int(datetime.utcnow().timestamp()),
            "exp": int((datetime.utcnow() + timedelta(hours=1)).timestamp()),
            "auth_time": int(datetime.utcnow().timestamp())
        }
        
        service = FirebaseService(auth_provider=mock_auth_provider)
        result = service.verify_token("valid_token")
        
        assert "uid" in result
        assert "email" in result
        assert "email_verified" in result
        assert result["uid"] == "user_123"

    def test_expired_token_handling(self, mock_auth_provider):
        """Test expired token raises exception"""
        mock_auth_provider.verify_id_token.side_effect = Exception("Token expired")
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        with pytest.raises(Exception) as exc_info:
            service.verify_token("expired_token")
        
        assert "Token expired" in str(exc_info.value)

    def test_malformed_token_handling(self, mock_auth_provider):
        """Test malformed token raises exception"""
        mock_auth_provider.verify_id_token.side_effect = Exception("Invalid token format")
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        with pytest.raises(Exception) as exc_info:
            service.verify_token("malformed_token")
        
        assert "Invalid token format" in str(exc_info.value)

    def test_token_from_different_project(self, mock_auth_provider):
        """Test token from different Firebase project raises exception"""
        mock_auth_provider.verify_id_token.side_effect = Exception("Project ID mismatch")
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        with pytest.raises(Exception) as exc_info:
            service.verify_token("wrong_project_token")
        
        assert "Project ID mismatch" in str(exc_info.value)


class TestFirebaseConnectionMocking:
    """Test Firebase connection can be properly mocked in tests"""

    def test_mock_firebase_for_testing(self):
        """Test Firebase can be completely mocked for unit tests"""
        mock_auth = MagicMock()
        mock_auth.verify_id_token.return_value = {
            "uid": "test_123",
            "email": "test@test.com"
        }
        
        mock_firestore = MagicMock()
        mock_client = MagicMock()
        mock_firestore.client.return_value = mock_client
        
        service = FirebaseService(
            auth_provider=mock_auth,
            firestore_provider=mock_firestore
        )
        
        # Test auth
        token_result = service.verify_token("test_token")
        assert token_result["uid"] == "test_123"
        
        # Test firestore
        client = service.get_firestore_client()
        assert client is mock_client

    def test_dependency_injection_allows_testing(self, mock_auth_provider, mock_firestore_provider):
        """Test dependency injection makes testing easier"""
        # This test demonstrates how DI makes testing cleaner
        service = FirebaseService(
            auth_provider=mock_auth_provider,
            firestore_provider=mock_firestore_provider
        )
        
        # Can easily test without real Firebase connection
        result = service.verify_token("test_token")
        client = service.get_firestore_client()
        
        assert result is not None
        assert client is not None


class TestFirebaseCredentialsHandling:
    """Test Firebase credentials handling"""

    def test_service_handles_missing_credentials_gracefully(self):
        """Test service initialization with missing credentials"""
        # This would be tested in integration tests with real Firebase
        # Unit tests just verify the structure exists
        service = get_firebase_service()
        assert service is not None

    def test_mock_credentials_in_tests(self, mock_auth_provider):
        """Test using mock credentials in tests"""
        # Mock provider doesn't need real credentials
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        # Can verify tokens without real Firebase connection
        result = service.verify_token("mock_token")
        assert result["uid"] == "test_user_123"


class TestFirestoreIntegration:
    """Test Firestore integration with DI"""

    def test_firestore_client_accessible(self, mock_firestore_provider):
        """Test Firestore client can be accessed through service"""
        service = FirebaseService(firestore_provider=mock_firestore_provider)
        
        client = service.get_firestore_client()
        
        assert client is not None
        mock_firestore_provider.client.assert_called_once()

    def test_firestore_can_be_mocked(self):
        """Test Firestore operations can be mocked for testing"""
        mock_firestore = MagicMock()
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_doc = MagicMock()
        
        # Setup mock chain
        mock_firestore.client.return_value = mock_client
        mock_client.collection.return_value = mock_collection
        mock_collection.document.return_value = mock_doc
        mock_doc.get.return_value.to_dict.return_value = {"data": "test"}
        
        service = FirebaseService(firestore_provider=mock_firestore)
        client = service.get_firestore_client()
        
        # Can mock Firestore operations
        doc = client.collection("test").document("doc_id").get()
        result = doc.to_dict()
        
        assert result["data"] == "test"


class TestFirebaseServiceLogging:
    """Test Firebase service logging"""

    def test_verify_token_logs_success(self, mock_auth_provider, caplog):
        """Test successful token verification is logged"""
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        with caplog.at_level("INFO"):
            service.verify_token("test_token")
        
        assert "verify_token: Entry" in caplog.text
        assert "verify_token: Success" in caplog.text

    def test_verify_token_logs_failure(self, mock_auth_provider, caplog):
        """Test failed token verification is logged"""
        mock_auth_provider.verify_id_token.side_effect = Exception("Test error")
        service = FirebaseService(auth_provider=mock_auth_provider)
        
        with caplog.at_level("ERROR"):
            try:
                service.verify_token("invalid_token")
            except Exception:
                pass
        
        assert "verify_token: Failure" in caplog.text
