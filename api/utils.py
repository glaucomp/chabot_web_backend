from .models import ConversationHistory
from django.utils import timezone
import openai
from api.services.chatbot import OPENAI_API_KEY

client = openai.OpenAI(api_key=OPENAI_API_KEY)

FLOW_DEFINITION = {
    "level_1_industry": {"next": "level_2_business_status"},
    "level_2_business_status": {
        "Good": "level_3_good_industry_issue",
        "Bad": "level_3_bad_improve",
        "Ok": "level_3_ok_share"
    },
    "level_3_good_industry_issue": {
        "YES": "level_4_tell_more_good",
        "NO": "level_4_good_no_issue"
    },
    "level_3_bad_improve": {
        "YES": "level_4_tell_more_bad",
        "NO": "level_4_bad_no_improve"
    },
    "level_3_ok_share": {
        "YES": "level_4_tell_more_ok",
        "NO": "level_4_ok_no_share"
    },
    "level_4_tell_more_good": {
        "YES": "level_5_offer_solution_good",
        "NO": "level_5_other_problems"
    },
    "level_4_good_no_issue": {"next": "level_5_other_problems"},
    "level_4_tell_more_bad": {
        "YES": "level_5_offer_solution_bad",
        "NO": "level_5_other_problems"
    },
    "level_4_bad_no_improve": {"next": "level_5_other_problems"},
    "level_4_tell_more_ok": {
        "YES": "level_5_offer_solution_ok",
        "NO": "level_5_other_problems"
    },
    "level_4_ok_no_share": {"next": "level_5_other_problems"},
}

def get_varied_question(original_question):
    prompt = f"""
    I'm having a friendly chat with a user. I've already asked this question once, but I don't want to sound repetitive or robotic. 
    Could you please help me rewrite the following question in a slightly different, conversational, and friendly manner?

    Original question: "{original_question}"

    Provide ONLY the rephrased, friendly question—no quotes, no extra text.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0.7
    )

    varied_question = response.choices[0].message.content.strip()
    return varied_question if varied_question else original_question

def add_conversation_step(conversation_id, level, node_id, question, response=None):
    conversation, created = ConversationHistory.objects.get_or_create(
        conversation_id=conversation_id,
        defaults={"history": []}
    )

    step = {
        "step": len(conversation.history) + 1,
        "level": level,
        "node_id": node_id,
        "question": question,
        "response": response,
        "timestamp": timezone.now().isoformat() if response else None
    }

    conversation.history.append(step)
    conversation.updated_at = timezone.now()
    conversation.save()

    return conversation

def get_next_step(conversation):
    history = conversation.history

    if not history:
        return "level_1_industry"

    current_step = history[-1]
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

    Is the user's response relevant and clearly answers the question?
    Answer strictly with "YES" if it answers correctly, or "NO" if it doesn't.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3,
        temperature=0
    )

    answer = response.choices[0].message.content.strip().upper()
    return answer == "YES"

def classify_response_with_ai_level_2(question, user_response, valid_categories):
    prompt = f"""
    Categorize the user's response to the following question into one of these categories: {', '.join(valid_categories)}.

    Question: "{question}"
    User's response: "{user_response}"

    Respond ONLY with one of these categories if it clearly matches.
    If it does not clearly match any of the categories, respond ONLY with "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip()
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