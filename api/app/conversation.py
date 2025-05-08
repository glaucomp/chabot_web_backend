import os
import logging
import time

from openai import OpenAI
from datetime import datetime

from ai_config.ai_constants import (
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    MAX_TOKENS,
    MAX_TEMPERATURE,
    LANGUAGE_DEFAULT,
)

from ai_config.ai_constants import (
    OPENAI_MODEL,
    OPENAI_TIMEOUT,
    MAX_TOKENS,
    MAX_TEMPERATURE,
    LANGUAGE_DEFAULT,
)

from ai_config.ai_prompts import (
    FIRST_MESSAGE_PROMPT,
)

from api.agents import get_specialist_agent
from api.chatbot import (
    chatbot,
)
from api.services.chatbot import OPENAI_API_KEY
from api.services.config import CHROMA_DIR

from .mongo import MongoDB



logger = logging.getLogger(__name__)
    

def prompt_conversation_site(
    user_prompt,
    conversation_id,
    language_code=LANGUAGE_DEFAULT,
):

    logger.info(f"Starting prompt_conversation_site request - Language: {language_code}")

    try:
        db = MongoDB.get_db()

        existing_conversation = db.conversations.find_one(
            {"session_id": conversation_id},
            {"messages": 1, "state": 1, "confirmed_topic": 1, "confirmed_action": 1, "_id": 0},
        ) or {}

        messages = existing_conversation.get("messages", [{"role": "system", "content": FIRST_MESSAGE_PROMPT}])

        messages.append({
            "role": "user",
            "content": user_prompt,
            "timestamp": datetime.now().isoformat(),
        })

        conversation_state = existing_conversation.get("state", "identifying_topic")
        confirmed_topic = existing_conversation.get("confirmed_topic")
        confirmed_action = existing_conversation.get("confirmed_action")

        if conversation_state == "identifying_topic":
            confirmed_topic = chatbot.initial_agent.identify_topic(user_prompt)

            if confirmed_topic in chatbot.topics:
                followup_question = chatbot.initial_agent.client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": f"Casually confirm the user's selected topic '{confirmed_topic}' and ask whether they want to create something new or improve something existing. Be friendly, conversational, and concise."}
                    ],
                    temperature=0.7,
                    max_tokens=60
                ).choices[0].message.content.strip()

                db.conversations.update_one(
                    {"session_id": conversation_id},
                    {"$set": {
                        "confirmed_topic": confirmed_topic,
                        "state": "topic_confirmed",
                        "messages": messages + [{"role": "assistant", "content": followup_question}],
                        "updated_at": datetime.now().isoformat()
                    }},
                    upsert=True
                )

                return {
                    "generation": followup_question,
                    "conversation_id": conversation_id,
                    "language": language_code,
                    "confirmation_required": False
                }

            else:
                clarifying_question = chatbot.initial_agent.ask_clarifying_question(user_prompt)

                db.conversations.update_one(
                    {"session_id": conversation_id},
                    {"$set": {
                        "state": "identifying_topic",
                        "messages": messages + [{"role": "assistant", "content": clarifying_question}],
                        "updated_at": datetime.now().isoformat()
                    }},
                    upsert=True
                )

                return {
                    "generation": clarifying_question,
                    "conversation_id": conversation_id,
                    "language": language_code,
                    "confirmation_required": True
                }

        elif conversation_state == "topic_confirmed":
            confirmed_action = chatbot.initial_agent.determine_next_action(confirmed_topic, user_prompt)

            # Pergunta clara para validar explicitamente a ação com o usuário
            action_confirmation_question = chatbot.initial_agent.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": f"""
                        Confirm casually and explicitly: Does the user want to '{confirmed_action}' something related to '{confirmed_topic}'?
                        Ask the user explicitly for confirmation with YES or NO.
                        Be brief, conversational, and friendly.
                    """}
                ],
                temperature=0.7,
                max_tokens=60
            ).choices[0].message.content.strip()

            db.conversations.update_one(
                {"session_id": conversation_id},
                {"$set": {
                    "confirmed_action": confirmed_action,
                    "state": "awaiting_action_confirmation",
                    "messages": messages + [{"role": "assistant", "content": action_confirmation_question}],
                    "updated_at": datetime.now().isoformat()
                }},
                upsert=True
            )

            return {
                "generation": action_confirmation_question,
                "conversation_id": conversation_id,
                "language": language_code,
                "confirmation_required": True
            }

        elif conversation_state == "awaiting_action_confirmation":
            user_confirmation = user_prompt.strip().lower()

            if user_confirmation in ["yes", "yeah", "yep", "correct", "sure"]:
                # Confirmado claramente, avançar para action_confirmed
                specialist_question = chatbot.initial_agent.client.chat.completions.create(
                    model="gpt-4-turbo",
                    messages=[
                        {"role": "system", "content": f"""
                            Enthusiastically acknowledge the user's choice to '{confirmed_action}' regarding '{confirmed_topic}'.
                            Ask them clearly and naturally to provide more details about their specific goal or requirement.
                            Keep it brief and friendly.
                        """}
                    ],
                    temperature=0.7,
                    max_tokens=60
                ).choices[0].message.content.strip()

                db.conversations.update_one(
                    {"session_id": conversation_id},
                    {"$set": {
                        "state": "action_confirmed",
                        "messages": messages + [{"role": "assistant", "content": specialist_question}],
                        "updated_at": datetime.now().isoformat()
                    }},
                    upsert=True
                )

                return {
                    "generation": specialist_question,
                    "conversation_id": conversation_id,
                    "language": language_code,
                    "confirmation_required": False
                }

            elif user_confirmation in ["no", "nope", "nah", "incorrect"]:
                # Não confirmado, pergunta claramente o que deseja
                retry_question = "Oops, sorry about that! Could you clarify explicitly if you'd like to 'create something new' or 'fix/improve something existing'?"

                db.conversations.update_one(
                    {"session_id": conversation_id},
                    {"$set": {
                        "state": "topic_confirmed",  # volta claramente para determinar novamente
                        "confirmed_action": None,  # reseta a ação para redeterminar
                        "messages": messages + [{"role": "assistant", "content": retry_question}],
                        "updated_at": datetime.now().isoformat()
                    }},
                    upsert=True
                )

                return {
                    "generation": retry_question,
                    "conversation_id": conversation_id,
                    "language": language_code,
                    "confirmation_required": True
                }

            else:
                clarification_response = chatbot.initial_agent.client.chat.completions.create(
                        model="gpt-4-turbo",
                            messages=[
                                {"role": "system", "content": "Apologize casually for misunderstanding and clearly ask the user again if they want to 'create something new' or 'fix/improve something existing'. Keep it brief and friendly."}
                            ],
                            temperature=0.7,
                            max_tokens=60
                        ).choices[0].message.content.strip()

                db.conversations.update_one(
                    {"session_id": conversation_id},
                        {"$set": {
                                "state": "awaiting_action_confirmation",
                                "messages": messages + [{"role": "assistant", "content": clarification_response}],
                                "updated_at": datetime.now().isoformat()
                        }},
                            upsert=True
                        )

                return {
                            "generation": clarification_response,
                            "conversation_id": conversation_id,
                            "language": language_code,
                            "confirmation_required": True
                        }

            
        # Estado ação confirmada: chamar agente especialista
        elif conversation_state == "action_confirmed":

            specialist_agent = get_specialist_agent(
                    confirmed_topic, 
                    OPENAI_API_KEY, 
                    CHROMA_DIR
                )
            
            specialist_response = specialist_agent.provide_solution(user_prompt, confirmed_action)

            messages.append({
                "role": "assistant",
                "content": specialist_response,
                "timestamp": datetime.now().isoformat()
            })

            db.conversations.update_one(
                {"session_id": conversation_id},
                {"$set": {
                    "messages": messages,
                    "updated_at": datetime.now().isoformat()
                }},
                upsert=True
            )

            return {
                "generation": specialist_response,
                "conversation_id": conversation_id,
                "language": language_code,
                "topic": confirmed_topic,
                "action": confirmed_action,
                "confirmation_required": False
            }


        else:
            logger.warning(f"Unrecognized conversation state '{conversation_state}', resetting to 'identifying_topic'.")

            reset_question = chatbot.initial_agent.ask_clarifying_question(user_prompt)

            db.conversations.update_one(
                {"session_id": conversation_id},
                {"$set": {
                    "state": "identifying_topic",
                    "messages": messages + [{"role": "assistant", "content": reset_question}],
                    "updated_at": datetime.now().isoformat()
                }},
                upsert=True
            )

            return {
                "generation": reset_question,
                "conversation_id": conversation_id,
                "language": language_code,
                "confirmation_required": True
            }

    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        raise

def prompt_conversation_image(
    conversation_id,
    image_base64,
):
    try:
        try:
            ai_response = chatbot.read_image_response(image_base64)
        except Exception as oe:
            logger.error(f"OpenAI error: {str(oe)}")
            raise
        return {
            "generation": ai_response,
            "conversation_id": conversation_id,
        }
    except Exception as e:
        logger.error(f"Error in prompt_conversation_site: {str(e)}", exc_info=True)
        raise

def prompt_conversation_agent_ai(
    user_prompt,
   ):

    try:
        # Vector store retrieval
        vector_start = time.time()
        docs_retrieve = []
        try:

            # Exception handling for user prompt
            if user_prompt.lower().strip() in ["ok", "like", "boss", "yes", "no","tq","thanks"]:
                 docs_retrieve = []
            else:
                docs_retrieve = chatbot.brain.query(user_prompt)

            for i, doc in enumerate(docs_retrieve, start=1):
                print(f"📌 Result {i}:")
                print(f"Content: {doc.page_content}\n")
                print(f"Metadata: {doc.metadata}\n")
                print("=" * 50)

            logger.debug(
                f"Vector store retrieval completed in {time.time() - vector_start:.2f}s"
            )
            return docs_retrieve
        
        except Exception as ve:
            logger.error(f"Vector store error: {str(ve)}")
            docs_retrieve = []
            print(docs_retrieve)

    except Exception as e:
        logger.error(f"Error in prompt_conversation_site: {str(e)}", exc_info=True)
        raise


# Configurações
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_MODEL = "grok-3-mini"  # ou "llama3-70b-8192"
MAX_TEMPERATURE = 0.3
MAX_TOKENS = 1024
GROK_TIMEOUT = 60

# Cliente Grok/x.ai
client = OpenAI(
    api_key=GROK_API_KEY,
    base_url="https://api.x.ai/v1",
    timeout=GROK_TIMEOUT
)

def prompt_conversation_grok_admin(
    user_prompt,
    conversation_id
):
    start_time = time.time()
    logger = logging.getLogger("conversation")

    db = MongoDB.get_db()
    logger.debug(f"MongoDB connection established in {time.time() - start_time:.2f}s")

    existing_conversation = db.conversations.find_one(
        {"session_id": conversation_id},
        {"messages": 1, "_id": 0},
    )

    messages = existing_conversation.get("messages", []) if existing_conversation else [
        {"role": "system", "content": FIRST_MESSAGE_PROMPT}
    ]

    # Add user message
    messages.append({
        "role": "user",
        "content": user_prompt,
        "timestamp": datetime.now().isoformat(),
    })

    # Vector store retrieval
    docs_retrieve = []
    if user_prompt.lower().strip() not in ["ok", "like", "boss", "yes", "no", "tq", "thanks"]:
        try:
            docs_retrieve = chatbot.brain.query(user_prompt)
        except Exception as ve:
            logger.error(f"Vector store error: {str(ve)}")

    try:
        static_chunks = chatbot.brain.vector_store.similarity_search(
            query=user_prompt,
            k=3,
            filter={"category": "static_rules"}
        )
        docs_retrieve += static_chunks
    except Exception as ve:
        logger.error(f"Vector store static search error: {str(ve)}")

    combined_context = ""
    if docs_retrieve:
        combined_context = (
            "Boss, here’s what we found in the official 4D Joker knowledge base that may help:\n\n"
            + "\n\n---\n\n".join([doc.page_content for doc in docs_retrieve])
        )

    language_prompts = {
        "en": "Please respond only in English.",
        "ms_MY": "Sila balas dalam Bahasa Melayu sahaja.",
        "zh_CN": "请只用中文回复。",
        "zh_TW": "請只用中文回覆。",
    }

    language_instruction = language_prompts.get(language_code, language_prompts["ms_MY"])

    messages_history = [
        {"role": "system", "content": language_instruction}
    ]

    if combined_context:
        messages_history.insert(0, {"role": "system", "content": combined_context})

    messages_history += [{"role": m["role"], "content": m["content"]} for m in messages]

    try:
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=messages_history,
            temperature=MAX_TEMPERATURE,
            max_tokens=MAX_TOKENS,
            timeout=GROK_TIMEOUT,
        )

        ai_response = response.choices[0].message.content

        messages.append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat(),
        })

        conversation = {
            "session_id": conversation_id,
            "admin_id": admin_id,
            "bot_id": bot_id,
            "user_id": user_id,
            "language": language_code,
            "messages": messages,
            "updated_at": datetime.now().isoformat(),
        }

        db.conversations.update_one(
            {"session_id": conversation_id},
            {"$set": conversation},
            upsert=True
        )

        return {
            "generation": ai_response,
            "conversation_id": conversation_id,
            "language": language_code,
        }
    except Exception as e:
        logger.error(f"Error in prompt_conversation_site: {str(e)}", exc_info=True)
        raise