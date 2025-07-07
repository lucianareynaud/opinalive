from ..config import settings
import logging

logger = logging.getLogger(__name__)

class StorageService:
    """
    Simplified storage service - no audio blob storage needed
    Only transcripts are saved in the database
    """
    
    def __init__(self):
        # No external storage needed
        logger.info("StorageService initialized - database-only mode")
    
    async def upload_audio(self, file_bytes: bytes, file_name: str) -> str:
        """
        No audio upload needed - return empty string
        Audio processing will be done in-memory only
        """
        logger.info(f"Skipping audio upload for {file_name} - database-only mode")
        return ""
    
    async def delete_audio(self, file_name: str) -> bool:
        """
        No audio deletion needed
        """
        logger.info(f"Skipping audio deletion for {file_name} - database-only mode")
        return True 