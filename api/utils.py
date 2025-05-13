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

    if user_response:
        next_node_id = FLOW_DEFINITION.get(current_node_id, {}).get(user_response)
        if not next_node_id:
            next_node_id = FLOW_DEFINITION.get(current_node_id, {}).get("next")
    else:
        next_node_id = current_node_id  # Ainda aguardando uma resposta válida.

    # fallback seguro
    if not next_node_id:
        next_node_id = "level_1_industry"

    return next_node_id

def validate_response_with_ai(question, user_response):
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