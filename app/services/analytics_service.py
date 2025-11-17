import logging
from datetime import datetime
from app.core.firebase import get_firestore_client

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self):
        # Firebase Admin SDK
        self.db = get_firestore_client()
        self.analytics_collection = 'analytics_events'  # For Firebase Analytics
        self.crashlytics_collection = 'crashlytics_errors'  # For Crashlytics-style error tracking
        self.logger = logging.getLogger(__name__)
    
    def log_event(
        self,
        event_name: str,
        user_id: str = None,
        parameters: dict = None,
    ):
        """
        Log analytics event to Firebase Analytics (via Firestore).
        Use this for tracking user actions and feature usage.
        """
        logger.info(f"log_event: Entry - {event_name}, user: {user_id}")
        
        try:
            event_data = {
                'event_name': event_name,
                'user_id': user_id,
                'parameters': parameters or {},
                'timestamp': datetime.utcnow()
            }
            
            # Store in Firestore for Firebase Analytics integration
            self.db.collection(self.analytics_collection).add(event_data)
            logger.info(f"log_event: Success - {event_name}")
            
        except Exception as e:
            # Analytics failures should not break main functionality
            logger.error(f"log_event: Failure - {e}")
    
    def log_crash(
        self,
        error: str,
        action: str,
        user_id: str = None,
        parameters: dict = None,
        stack_trace: str = None,
        fatal: bool = False
    ):
        """
        Log error to Crashlytics-style error tracking (via Firestore).
        Use this for tracking errors, exceptions, and crashes.
        """
        logger.info(f"log_crash: Entry - {action}, error: {error}, fatal: {fatal}")
        
        try:
            error_data = {
                'action': action,
                'user_id': user_id,
                'error_message': error,
                'stack_trace': stack_trace,
                'parameters': parameters or {},
                'fatal': fatal,
                'timestamp': datetime.utcnow()
            }
            
            # Store in Firestore for Crashlytics-style error tracking
            self.db.collection(self.crashlytics_collection).add(error_data)
            logger.info(f"log_crash: Success - {action}")
            
        except Exception as e:
            # Error logging failures should not break main functionality
            logger.error(f"log_crash: Failure - {e}")
    
    def log_success(
        self,
        action: str,
        user_id: str = None,
        parameters: dict = None
    ):
        """
        Log successful action to Firebase Analytics.
        Tracks successful operations for product analytics.
        """
        self.log_event(
            event_name=f'{action}_success',
            user_id=user_id,
            parameters={
                'status': 'success',
                **(parameters or {})
            }
        )
    
    def log_failure(
        self,
        action: str,
        error: str,
        user_id: str = None,
        parameters: dict = None,
        stack_trace: str = None
    ):
        """
        Log failed action to BOTH Firebase Analytics and Crashlytics.
        - Analytics: Tracks failure rate for product metrics
        - Crashlytics: Tracks errors for debugging and monitoring
        """
        logger.info(f"log_failure: Entry - {action}, error: {error}")
        
        try:
            # 1. Log to Firebase Analytics (for product metrics)
            self.log_event(
                event_name=f'{action}_failure',
                user_id=user_id,
                parameters={
                    'status': 'failure',
                    'error': error,
                    **(parameters or {})
                }
            )
            
            # 2. Log to Crashlytics-style error tracking (for error monitoring)
            self.log_crash(
                error=error,
                action=action,
                user_id=user_id,
                parameters=parameters,
                stack_trace=stack_trace,
                fatal=False  # Non-fatal since we're catching and handling it
            )
            
            logger.info(f"log_failure: Success - {action}")
        except Exception as e:
            logger.error(f"log_failure: Failure - {e}")

