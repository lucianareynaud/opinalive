import asyncio
import json
import logging
from typing import Optional
import os
from pathlib import Path
import subprocess
from ..config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    def __init__(self):
        """Initialize WhatsApp service with Baileys"""
        self.process = None
        self.connected = False
        self.auth_path = Path("./auth")
        self.media_path = Path("./audios")
        
        # Create directories if they don't exist
        self.auth_path.mkdir(exist_ok=True)
        self.media_path.mkdir(exist_ok=True)
        
        # Initialize Node.js process
        self._start_baileys()
    
    def _start_baileys(self):
        """Start Baileys Node.js process"""
        try:
            # Start Node.js process
            self.process = subprocess.Popen(
                ["node", "whatsapp/baileys-listener.js"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            logger.info("Started Baileys WhatsApp listener")
        except Exception as e:
            logger.error(f"Failed to start Baileys process: {e}")
            self.process = None
    
    async def check_connection(self) -> bool:
        """Check if WhatsApp is connected"""
        if not self.process:
            return False
            
        # Check if process is still running
        if self.process.poll() is not None:
            logger.error("Baileys process died, restarting...")
            self._start_baileys()
            return False
            
        return True
    
    async def send_text(self, to_number: str, message: str) -> bool:
        """Send text message via Baileys"""
        if not await self.check_connection():
            logger.warning("Cannot send text - Baileys not connected")
            return False
            
        # Normalize phone number
        if not to_number.startswith("+"):
            to_number = f"+{to_number}"
        to_number = to_number.replace("+", "").replace("-", "").replace(" ", "") + "@s.whatsapp.net"
        
        try:
            # Send message through Node.js IPC
            message_data = {
                "type": "send_message",
                "to": to_number,
                "message": message
            }
            self.process.stdin.write(json.dumps(message_data) + "\n")
            self.process.stdin.flush()
            return True
        except Exception as e:
            logger.error(f"Error sending text message: {e}")
            return False
    
    async def send_template(self, to_number: str, tenant_name: str) -> bool:
        """Send feedback request message"""
        message = f"Olá! A {tenant_name} gostaria de saber sua opinião. Por favor, envie um áudio com seu feedback."
        return await self.send_text(to_number, message)
    
    async def download_media(self, media_id: str) -> Optional[bytes]:
        """Get media file from filesystem saved by Baileys"""
        try:
            media_file = self.media_path / f"{media_id}.ogg"
            if not media_file.exists():
                logger.error(f"Media file {media_id} not found")
                return None
                
            with open(media_file, "rb") as f:
                content = f.read()
                
            # Delete file after reading
            media_file.unlink()
            return content
        except Exception as e:
            logger.error(f"Error reading media file: {e}")
            return None
            
    def __del__(self):
        """Cleanup when service is destroyed"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill() 