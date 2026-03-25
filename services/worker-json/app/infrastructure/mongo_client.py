"""MongoDB client and lifecycle management for the JSON Worker."""

import logging
from typing import Any, Dict

from motor.motor_asyncio import AsyncIOMotorClient

from app.infrastructure.config import settings

logger = logging.getLogger(__name__)

class MongoDBClient:
    """Manages the MongoDB connection pool."""
    
    client: AsyncIOMotorClient | None = None
    
    @classmethod
    async def connect(cls) -> None:
        """Initialize the Motor async client."""
        if cls.client is None:
            logger.info("connecting_to_mongodb", uri=settings.MONGO_URI)
            cls.client = AsyncIOMotorClient(settings.MONGO_URI)
            
            # Verify connection
            try:
                await cls.client.admin.command('ping')
                logger.info("mongodb_connection_successful")
            except Exception as e:
                logger.error("mongodb_connection_failed", error=str(e))
                raise

    @classmethod
    async def close(cls) -> None:
        """Close the Motor async client."""
        if cls.client is not None:
            cls.client.close()
            cls.client = None
            logger.info("mongodb_connection_closed")

    @classmethod
    def get_db(cls) -> Any:
        """Get the analysis database instance."""
        if cls.client is None:
            raise RuntimeError("MongoDB client is not initialized. Call connect() first.")
        return cls.client[settings.MONGO_DB]

mongodb = MongoDBClient()
