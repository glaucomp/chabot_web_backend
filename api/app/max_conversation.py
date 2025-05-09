import logging
from api.agents.max_agent import MaxAgent
from .mongo import MongoDB
from api.services.chatbot import OPENAI_API_KEY

from datetime import datetime

logger = logging.getLogger(__name__)

max_agent = MaxAgent(OPENAI_API_KEY)

def max_phone_conversation(user_prompt, conversation_id):
    logger.info(f"📞 Max phone conversation - ID: {conversation_id}")

    db = MongoDB.get_db()

    existing_conversation = db.max_conversations.find_one({"session_id": conversation_id}) or {}

    messages = existing_conversation.get("messages", [])

    messages.append({
        "role": "user",
        "content": user_prompt,
        "timestamp": datetime.now().isoformat()
    })

    max_response = max_agent.provide_human_like_response(user_prompt)

    messages.append({
        "role": "assistant",
        "content": max_response,
        "timestamp": datetime.now().isoformat()
    })

    # Salva no histórico exclusivo de Max
    db.max_conversations.update_one(
        {"session_id": conversation_id},
        {"$set": {
            "messages": messages,
            "updated_at": datetime.now().isoformat()
        }},
        upsert=True
    )

    return {
        "generation": max_response,
        "conversation_id": conversation_id
    }