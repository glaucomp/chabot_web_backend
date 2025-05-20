from .models import ConversationFlow , ConversationHistory
from django.utils import timezone
import openai
from api.services.chatbot import OPENAI_API_KEY
import logging
import random

logger = logging.getLogger(__name__)

client = openai.OpenAI(api_key=OPENAI_API_KEY)

FLOW_DEFINITION = {
    "level_1_industry": {"next": "level_2_business_status"},
    "level_2_business_status": {
        "POSITIVE": "level_2_positive",
        "NEGATIVE": "level_3_negative",
        "VAGUE": "level_2_vague",
        "REJECT": "level_2_reject",
    },
    "level_2_vague": {
        "NEXT": "level_3_negative",
    },
    "level_2_reject": {
        "NEXT": "level_3_negative",
    },
    "level_2_positive": {
        "YES": "level_3_negative",
        "NO": "level_2_business_status"
    },
    "level_3_negative": {
        "YES": "level_4_tell_more_good",
        "NO": "level_4_deal_with"
    },
    "level_4_tell_more_good": {
        "YES": "level_5_ask_more_problems",
        "NO": "level_5_glad_to_hear"
    },
    "level_4_deal_with": {
        "YES": "level_4_tell_more_good",
    },
    "level_5_you_must_be_top": { 
        "YES": "level_4_tell_more_good",
        "NO": "level_5_glad_to_hear",
    },
    "level_5_glad_to_hear": {
        "YES": "@@@REFERRAL@@@",
        "NO": "level_6_best_of_luck", 
    },
    "level_5_ask_more_problems": {"YES": "@@@EMAIL@@@"},
    "level_6_best_of_luck": {"YES": "@@@SAVE CONVERSATION@@@"},
}

def get_varied_question(original_question, conversation_id):
    history = ConversationHistory.objects.filter(conversation_id=conversation_id).first()

    if history and history.history:
        history_text = "\n".join(
            f'{step["sender"]}: {step["message"]}'
            for step in history.history[-6:]
        )

        prompt = f"""
        I'm chatting informally with a user. Here's our recent interaction:

        {history_text}

        To avoid sounding repetitive, could you please naturally and informally rephrase this next question?

        Original question: "{original_question}"

        Provide ONLY the naturally rephrased question—no quotes.

        Instructions:
        - Use Grant Cardone's sales techiques to make the question more engaging and natural.
        - Ask how the user how they are doing with what they are up to.
        - After find out how user is doing with they are up to, discover the user's problems and needs.
        - Before the original phase, be curious and exciting to learn more about user's business.
       
        """

        logger.info(f"[VARIED_QUESTION] Contextual history:\n{history_text}")

    else:
        casual_greetings = [
            "Hey there! Great to connect.",
            "Hi! Happy we can chat.",
            "Hello! Glad we're talking today.",
            "Hey! Good to meet you here.",
            "Hi there! Looking forward to our conversation."
        ]

        introductory_phrases = [
            "I'm curious to learn more about you.",
            "I'd love to hear about your experiences.",
            "It'd be great to know a bit more about you.",
            "I’m interested in finding out what you do.",
            "I'd really enjoy hearing your story."
        ]

        greeting = random.choice(casual_greetings)
        intro = random.choice(introductory_phrases)

        prompt = f"""
        I'm starting a warm and informal conversation. 
        Please rephrase the original question below following this friendly style exactly:
        
        "{greeting} {intro} [friendly rephrased main question]"

        Original question: "{original_question}"

        Provide ONLY your fully friendly rephrased sentence—no quotes, no extra text.
        """

        logger.info(f"[VARIED_QUESTION] New conversation, generated greeting:\n{greeting} {intro}")


    logger.info(f"[VARIED_QUESTION] Prompt enviado para OpenAI:\n{prompt}")

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=60,
        temperature=0.9
    )

    varied_question = response.choices[0].message.content.strip()

    return varied_question if varied_question else original_question

def add_conversation_step(conversation_id, level, node_id, question, response=None):
    conversation, created = ConversationFlow.objects.get_or_create(
        conversation_id=conversation_id,
        defaults={"flow": []}
    )
    step = {
        "step": len(conversation.flow) + 1,
        "level": level,
        "node_id": node_id,
        "question": question,
        "response": response,
        "timestamp": timezone.now().isoformat() if response else None
    }
    conversation.flow.append(step)
    conversation.updated_at = timezone.now()
    conversation.save()
    return conversation

def get_next_step(conversation):

    flow = conversation.flow

    if not flow:
        return "level_1_industry"

    current_step = flow[-1]
    current_node_id = current_step["node_id"]
    user_response = current_step.get("response")
   
    next_node_data = FLOW_DEFINITION.get(current_node_id, {})

    if user_response:
        next_node_id = next_node_data.get(user_response)
        if not next_node_id:
            next_node_id = next_node_data.get("next")
    else:
        next_node_id = current_node_id

    return next_node_id or "level_1_industry"

def validate_response_with_ai_level_1(question, user_response):
    prompt = f"""
    Question: "{question}"
    User's response: "{user_response}"

    Is the user's response relevant about his industry?
    Instructions:
    - If the user's response is relevant to the industry, answer strictly with "YES".
    - If the user's response is not relevant to the industry, use a friendly way to ask more infomation.
    Answer strictly with "YES" if it answers correctly, or "NO" if it doesn't.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3,
        temperature=0
    )

    answer = response.choices[0].message.content.strip().upper()
    logger.info(f"[VALIDATE_RESPONSE] Validate response with AI Level 1: {answer}")
    return answer == "YES"

def classify_response_with_ai_level_2_positive(question, user_response):
    valid_categories = ["YES", "NO"]

    prompt = f"""
        You are categorizing a user's response to the following question:

        Question:
        "{question}"

        User's response:
        "{user_response}"

        Instructions:
        - Respond ONLY with "yes" if the user's response clearly and explicitly indicates YES, AFFIRMATIVE, AGREEMENT, or confirms they have the specific issue described in the original question.
        - For ANY other response, including unclear, vague, different problems, or negative responses, respond ONLY with "no".

        Respond ONLY with the exact word: "YES" or "NO".
        """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip()
    return category if category in valid_categories else None

def classify_response_with_ai_level_vague_reject(question, user_response):
    valid_categories = ["NEXT"]
    prompt = f"""
        You are categorizing a user's response to the following question:
        Question:
        "{question}"
        User's response:
        "{user_response}"
        Instructions:
        - Respond ONLY with "next" if the user's response clearly answer the question.
        """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )
    category = response.choices[0].message.content.strip()
    return category if category in valid_categories else None

def classify_response_with_ai_level_2(question, user_response, valid_categories):
    
    prompt = f"""
    Categorize clearly the user's response to the following question into exactly one of these categories: {', '.join(valid_categories)}.".

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - Respond strictly "Positive" if the user's response the business is good or without any problems.
    - Respond strictly "Negative" if the user's response clearly indicates the business has problems.
    - Respond strictly "Reject" if the user's response clearly indicates rejection or refusal to provide the answer.
    - Respond strictly "Vague" if the user's response is unclear or does not clearly indicate either Positive or Negative or Vague.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    logger.info(f"[CLASSIFY_RESPONSE] Classify response with AI Level 2: {category}")

    return category if category in valid_categories else None

def classify_response_with_ai_level_3(question, user_response):
    valid_categories = ["YES", "NO"]
    
    prompt = f"""
    Categorize clearly the user's response to the following question into exactly one of these two categories: YES, NO.

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - Respond strictly "YES" if the user's response clearly indicates affirmation or agreement.
    - Respond strictly "NO" if the user's response clearly indicates denial or disagreement.
    - If the user's response is unclear or does not clearly indicate either YES or NO, respond strictly with "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_4(question, user_response):
    valid_categories = ["YES", "NO"]
    
    prompt = f"""
    Categorize the user's response to the following question clearly into one of these two categories: YES, NO.

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - If the user clearly indicates a positive, affirmative, or detailed response, answer ONLY "YES".
    - If the user clearly indicates a negative, denial, or refusal to provide details, answer ONLY "NO".
    - If the user's response is unclear or doesn't fit clearly, answer ONLY "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_4_deal_with(question, user_response):
    prompt = f"""
    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - Respond strictly with "YES" if the user's response explicitly confirms or positively answers the question.
    - If the user's response is negative, unclear, irrelevant, uncertain, or does not explicitly confirm, respond strictly with "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category == "YES" else None

def classify_response_with_ai_level_5_you_must_be_top(question, user_response):
    valid_categories = ["YES", "NO"]
    
    prompt = f"""
    Categorize the user's response to the following question clearly into one of these two categories: YES, NO.

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - If the user clearly indicates a positive, affirmative, or detailed response, answer ONLY "YES".
    - If the user clearly indicates a negative, denial, or refusal to provide details, answer ONLY "NO".
    - If the user's response is unclear or doesn't fit clearly, answer ONLY "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_5_glad_to_hear(question, user_response):
    valid_categories = ["YES", "NO"]
    
    prompt = f"""
    Categorize the user's response to the following question clearly into one of these two categories: YES, NO.

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - If the user clearly indicates a positive, affirmative, or detailed response, answer ONLY "YES".
    - If the user clearly indicates a negative, denial, or refusal to provide details, answer ONLY "NO".
    - If the user's response is unclear or doesn't fit clearly, answer ONLY "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_6_best_of_luck(question, user_response):
    prompt = f"""
    Determine if the user's response to the following question contains a valid email address.

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - If the user's response clearly includes a valid email address, respond strictly with "YES".
    - If the response clearly does NOT contain a valid email address, respond strictly with "NO".
    - If the user's response is unclear, respond strictly with "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return "YES" if category == "YES" else None

def execute_final_node_action(node_id, conversation_id, user_response):
    if node_id == "@@@REFERRAL@@@":
        return handle_referral(conversation_id, user_response)
    elif node_id == "@@@EMAIL@@@":
        return handle_email(conversation_id, user_response)
    elif node_id == "@@@SAVE CONVERSATION@@@":
        return save_conversation(conversation_id)
    else:
        return None

def handle_referral(conversation_id, user_response):
    return {
        "status": "referral_handled",
        "conversation_id": conversation_id,
        "details": user_response
    }

def handle_email(conversation_id, user_response):
    return {
        "status": "email_handled",
        "conversation_id": conversation_id,
        "email": user_response
    }

def save_conversation(conversation_id):
    return {
        "status": "conversation_saved",
        "conversation_id": conversation_id,
    }
