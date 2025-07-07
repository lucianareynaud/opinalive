import openai
from ..config import settings
import logging
import tempfile
import os

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        openai.api_key = settings.OPENAI_API_KEY
    
    async def transcribe_audio(self, audio_bytes: bytes) -> str:
        """
        Transcribe audio using OpenAI Whisper API
        """
        try:
            # Create temporary file to save audio
            with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
                temp_file.write(audio_bytes)
                temp_file_path = temp_file.name
            
            try:
                # Use OpenAI Whisper API for transcription
                with open(temp_file_path, 'rb') as audio_file:
                    response = await openai.Audio.atranscribe(
                        model="whisper-1",
                        file=audio_file,
                        language="pt"  # Portuguese
            )
            
                return response.text
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            raise

# Backward compatibility alias
DeepgramService = TranscriptionService 