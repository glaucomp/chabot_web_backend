import json, uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .utils import (
    get_varied_question,
    add_conversation_step,
    get_next_step,
    validate_response_with_ai_level_1,
    classify_response_with_ai_level_2,
    classify_response_with_ai_level_3,
    classify_response_with_ai_level_4,
    FLOW_DEFINITION,
)
from .models import ConversationHistory


QUESTION_TEXT_MAPPING = {
    "level_1_industry": "What [INDUSTRY] are you in?",
    "level_2_business_status": "How is business going?",
    "level_3_good_industry_issue": "I've heard about some common [INDUSTRY ISSUE] in your field. Are you facing any of them?",
    "level_3_bad_improve": "Tell me more about what you'd like to improve.",
    "level_3_ok_share": "Is there something interesting happening you'd like to share?",
    "level_4_tell_more_good": "Tell me more about it...",
    "level_4_good_no_issue": "Got it! Any other problems?",
    "level_4_tell_more_bad": "Tell me more about it...",
    "level_4_bad_no_improve": "Understood. Are there any other issues?",
    "level_4_tell_more_ok": "Tell me more about it...",
    "level_4_ok_no_share": "Got it. Any other concerns?",
    "level_5_offer_solution_good": "Here's what I can suggest...",
    "level_5_other_problems": "Are you facing any other issues?"
    # Continue conforme necessário...
}

@csrf_exempt
def conversation_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=400)

    if not request.body:
        return JsonResponse({"error": "Empty request body."}, status=400)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON provided."}, status=400)

    data = json.loads(request.body)
    conversation_id = data.get("conversation_id")
    user_response = data.get("response")

    if not conversation_id:
        # NOVA CONVERSA
        conversation_id = str(uuid.uuid4())
        next_node_id = "level_1_industry"
        original_question = QUESTION_TEXT_MAPPING[next_node_id]
        next_question = get_varied_question(original_question)

        conversation = ConversationHistory.objects.create(
            conversation_id=conversation_id,
            history=[{
                "step": 1,
                "level": 1,
                "node_id": next_node_id,
                "question": next_question,
                "response": None,
                "timestamp": None
            }],
        )

        return JsonResponse({
            "conversation_id": conversation_id,
            "next_step": {
                "node_id": next_node_id,
                "level": 1,
                "question": next_question
            },
            "history": conversation.history
        })

    # CONTINUAÇÃO DE UMA CONVERSA
    conversation = ConversationHistory.objects.filter(conversation_id=conversation_id).first()
    if not conversation:
        return JsonResponse({"error": "Invalid conversation_id provided."}, status=400)

    current_step = conversation.history[-1]
    current_question = current_step["question"]
    current_node_id = current_step["node_id"]
    current_level = current_step["level"]

    if not user_response:
        return JsonResponse({"error": "Response required for existing conversation."}, status=400)

    # -----------------------------------
    # ORGANIZAÇÃO PRINCIPAL POR LEVEL
    # -----------------------------------

    if current_node_id == "level_1_industry":
        if not validate_response_with_ai_level_1(current_question, user_response):
            return _error_response(conversation, current_step, "Your response didn't answer my question clearly.")

        current_step["response"] = user_response

    elif current_node_id == "level_2_business_status":
        valid_categories = list(FLOW_DEFINITION[current_node_id].keys())
        classified_category = classify_response_with_ai_level_2(current_question, user_response, valid_categories)

        if not classified_category:
            return _error_response(conversation, current_step, "Couldn't classify your response, please try again.")

        current_step["response"] = classified_category
        current_step["original_user_response"] = user_response

    elif current_node_id in ["level_3_good_industry_issue", "level_3_bad_improve", "level_3_ok_share"]:
        classified_category = classify_response_with_ai_level_3(current_question, user_response)

        if not classified_category:
            return _error_response(conversation, current_step, "Please clearly answer YES or NO.")

        current_step["response"] = classified_category
        current_step["original_user_response"] = user_response

    elif current_node_id in ["level_4_tell_more_good", "level_4_tell_more_bad", "level_4_tell_more_ok"]:
        classified_category = classify_response_with_ai_level_4(current_question, user_response)

        if not classified_category:
            return _error_response(conversation, current_step, "Please clearly indicate YES or NO.")

        current_step["response"] = classified_category
        current_step["original_user_response"] = user_response

    else:
        # Segurança para node_ids inesperados
        return JsonResponse({"error": "Unexpected conversation step."}, status=400)

    # Atualiza timestamp após validação
    current_step["timestamp"] = timezone.now().isoformat()
    conversation.updated_at = timezone.now()
    conversation.save()

    # Calcula próximo passo
    next_node_id = get_next_step(conversation)
    original_question = QUESTION_TEXT_MAPPING.get(next_node_id, "Could you elaborate more?")
    next_question = get_varied_question(original_question)
    next_level = current_level + 1

    # Salva imediatamente o próximo passo
    add_conversation_step(
        conversation_id=conversation_id,
        level=next_level,
        node_id=next_node_id,
        question=next_question,
        response=None
    )

    conversation.refresh_from_db()

    return JsonResponse({
        "conversation_id": conversation_id,
        "next_step": {
            "node_id": next_node_id,
            "level": next_level,
            "question": next_question
        },
        "history": conversation.history
    })

# -----------------------------------
# Helper (simplifica resposta de erro)
# -----------------------------------
def _error_response(conversation, current_step, error_message):
    return JsonResponse({
        "conversation_id": conversation.conversation_id,
        "next_step": {
            "node_id": current_step["node_id"],
            "level": current_step["level"],
            "question": f"Sorry, {error_message} {current_step['question']}"
        },
        "history": conversation.history,
        "error": error_message
    })