#!/usr/bin/env python3
"""
Database Connection Handler
Manages MongoDB connections and provides database access
"""

import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import MONGO_URL, DATABASE_NAME, LOG_LEVEL

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Enhanced MongoDB connection handler with error recovery"""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.connected = False
        self.connection_retries = 0
        self.max_retries = 3
        
    def connect(self):
        """Establish MongoDB connection with retry logic"""
        try:
            self.client = MongoClient(
                MONGO_URL,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                maxPoolSize=50,
                retryWrites=True
            )
            
            # Test connection
            self.client.admin.command('ping')
            self.db = self.client[DATABASE_NAME]
            self.connected = True
            self.connection_retries = 0
            
            logger.info("✅ MongoDB connected successfully")
            return True
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self.connection_retries += 1
            logger.error(f"❌ MongoDB connection failed (attempt {self.connection_retries}): {e}")
            
            if self.connection_retries < self.max_retries:
                logger.info(f"🔄 Retrying connection in 5 seconds...")
                import time
                time.sleep(5)
                return self.connect()
            else:
                logger.error("❌ Max retries reached. Using fallback mode.")
                self.connected = False
                return False
                
        except Exception as e:
            logger.error(f"❌ Unexpected database error: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info("🔌 MongoDB connection closed")
    
    def get_collection(self, collection_name):
        """Get collection with connection check"""
        if not self.connected or not self.db:
            if not self.connect():
                return None
        return self.db[collection_name]
    
    def is_connected(self):
        """Check if database is connected"""
        return self.connected
    
    def health_check(self):
        """Perform database health check"""
        try:
            if self.client:
                self.client.admin.command('ping')
                return True
        except Exception as e:
            logger.warning(f"Database health check failed: {e}")
            self.connected = False
        return False

# Global database instance
db_connection = DatabaseConnection()
