from firebase_admin import firestore
from app.core.firebase import get_firestore_client
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalyticsService:
    def __init__(self):
        self.db = get_firestore_client()
        self.events_collection = 'analytics_events'
        self.errors_collection = 'error_logs'
    
    def log_event(
        self,
        event_name: str,
        user_id: str = None,
        parameters: dict = None,
        status: str = 'success'
    ):
        """Log analytics event to Firestore"""
        logger.info(f"log_event: Entry - {event_name}, user: {user_id}, status: {status}")
        
        try:
            event_data = {
                'event_name': event_name,
                'user_id': user_id,
                'status': status,
                'parameters': parameters or {},
                'timestamp': datetime.utcnow(),
            }
            
            self.db.collection(self.events_collection).add(event_data)
            logger.info(f"log_event: Success - {event_name}")
        except Exception as e:
            logger.error(f"log_event: Failure - {e}")
    
    def log_success(
        self,
        action: str,
        user_id: str = None,
        parameters: dict = None
    ):
        """Log successful action"""
        self.log_event(
            event_name=f'{action}_success',
            user_id=user_id,
            parameters=parameters,
            status='success'
        )
    
    def log_failure(
        self,
        action: str,
        error: str,
        user_id: str = None,
        parameters: dict = None
    ):
        """Log failed action"""
        logger.info(f"log_failure: Entry - {action}, error: {error}")
        
        try:
            # Log to analytics
            self.log_event(
                event_name=f'{action}_failure',
                user_id=user_id,
                parameters={**(parameters or {}), 'error': error},
                status='failure'
            )
            
            # Log to error collection
            error_data = {
                'action': action,
                'user_id': user_id,
                'error': error,
                'parameters': parameters or {},
                'timestamp': datetime.utcnow(),
            }
            self.db.collection(self.errors_collection).add(error_data)
            
            logger.info(f"log_failure: Success - {action}")
        except Exception as e:
            logger.error(f"log_failure: Failure - {e}")

