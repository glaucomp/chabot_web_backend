import logging
from .services.chatbot import ChatBot

# create our gloabl variables
logger = logging.getLogger(__name__)

# Process docs
try:
    chatbot = ChatBot()
    logger.info("Chatbot is ready")
except Exception as e:
    logger.error(f"Chatbot initialization failed: {str(e)}")
    raise SystemExit(e)
 