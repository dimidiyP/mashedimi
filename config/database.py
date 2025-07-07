import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from typing import Optional, Dict, Any
import logging
from .settings import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database connection and management"""
    
    def __init__(self):
        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._async_client: Optional[AsyncIOMotorClient] = None
        self._async_db: Optional[Database] = None
        
    def connect(self) -> Database:
        """Connect to MongoDB (sync)"""
        if self._client is None:
            self._client = MongoClient(settings.MONGO_URL)
            self._db = self._client[settings.DB_NAME]
            logger.info(f"Connected to MongoDB: {settings.DB_NAME}")
        return self._db
    
    async def connect_async(self) -> Database:
        """Connect to MongoDB (async)"""
        if self._async_client is None:
            self._async_client = AsyncIOMotorClient(settings.MONGO_URL)
            self._async_db = self._async_client[settings.DB_NAME]
            logger.info(f"Connected to MongoDB (async): {settings.DB_NAME}")
        return self._async_db
    
    def get_collection(self, name: str) -> Collection:
        """Get a collection by name"""
        db = self.connect()
        return db[name]
    
    async def get_collection_async(self, name: str) -> Collection:
        """Get a collection by name (async)"""
        db = await self.connect_async()
        return db[name]
    
    def close(self):
        """Close database connections"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
        if self._async_client:
            self._async_client.close()
            self._async_client = None
            self._async_db = None
    
    def create_indexes(self):
        """Create database indexes for better performance"""
        try:
            # User collection indexes
            users_collection = self.get_collection("users")
            users_collection.create_index("user_id", unique=True)
            
            # Food analysis collection indexes
            food_collection = self.get_collection("food_analysis")
            food_collection.create_index([("user_id", 1), ("timestamp", -1)])
            food_collection.create_index("timestamp")
            
            # Movies collection indexes
            movies_collection = self.get_collection("movies")
            movies_collection.create_index([("user_id", 1), ("timestamp", -1)])
            movies_collection.create_index("user_id")
            
            # Health profiles collection indexes
            health_collection = self.get_collection("health_profiles")
            health_collection.create_index("user_id", unique=True)
            
            # Workouts collection indexes
            workouts_collection = self.get_collection("workouts")
            workouts_collection.create_index([("user_id", 1), ("timestamp", -1)])
            
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

# Global database manager instance
db_manager = DatabaseManager()