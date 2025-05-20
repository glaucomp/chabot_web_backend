import json, uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .utils import (
    get_varied_question,
    get_next_step,
    validate_response_with_ai_level_1,
    classify_response_with_ai_level_2,
    classify_response_with_ai_level_2_positive,
    classify_response_with_ai_level_vague_reject,
    classify_response_with_ai_level_3,
    classify_response_with_ai_level_4,
    classify_response_with_ai_level_4_deal_with,
    classify_response_with_ai_level_5_you_must_be_top,
    classify_response_with_ai_level_5_glad_to_hear,
    classify_response_with_ai_level_6_best_of_luck,
    execute_final_node_action,
    FLOW_DEFINITION,
)
from .models import ConversationFlow , ConversationHistory


QUESTION_TEXT_MAPPING = {
    "level_1_industry": "What INDUSTRY are you in?",
    "level_2_business_status": "That's interesting, How is business going?",
    "level_2_positive": "Great happy for you. I have heard in your industry you guys have INDUSTRY ISSUE is that something you have to deal with?",
    "level_2_vague": "I’m not sure I fully understand. Could you clarify how things are currently going with your business?",
    "level_2_reject": "That’s absolutely fine! I’d be happy to assist. How’s your business doing at the moment?",
    "level_3_negative": "Alright, let’s discuss this together. What specifically would you like to improve, or what’s the main pain point?",

    "level_4_tell_more_good": "Tell me more about it...",
    "level_4_deal_with": "I have heard in your industry you guys have [INDUSTRY ISSUE] is that something you have to deal with?",
    "level_5_you_must_be_top":"You must be top of your game. Here’s the thing… as M&J intel, i help all sorts of industries to figure out their problems. Do you want to share anything that has been bothering you?21",
    "level_5_glad_to_hear":"Im glad to hear that,I’m happy for you. I’m not sure if this is for you, but do you know anyone who would need my help?",
    "level_6_best_of_luck": "Best of luck in the future. Nice meeting you. If you ever want to pick up this conversation enter your email below.",
    
    "level_5_ask_more_problems": "Got it. Would you like to talk about other issues?",
    "level_5_offer_solution_good": "Here's what I can suggest...",

    "@@@EMAIL@@@": "Thank you! I'll follow up via email soon. Could you please confirm your email address?",
    "@@@REFERRAL@@@": "Fantastic! Could you please share the contact details of the person you'd like to refer?",
    "@@@SAVE CONVERSATION@@@": "I'll make sure our conversation is saved. If you need anything else, feel free to get back in touch!"

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

    conversation_id = data.get("conversation_id")
    user_response = data.get("response")

    if not conversation_id:
        # NOVA CONVERSA
        conversation_id = str(uuid.uuid4())
        next_node_id = "level_1_industry"
        original_question = QUESTION_TEXT_MAPPING[next_node_id]
        next_question = get_varied_question(original_question,conversation_id)

        flow = ConversationFlow.objects.create(
            conversation_id=conversation_id,
            flow=[{
                "step": 1,
                "level": 1,
                "node_id": next_node_id,
                "question": original_question,
                "response": None,
                "validated": False
            }],
        )

        history = ConversationHistory.objects.create(
            conversation_id=conversation_id,
            history=[
                {
                    "timestamp": timezone.now().isoformat(),
                    "sender": "AI",
                    "message": next_question
                }
            ]
        )

        return JsonResponse({
            "conversation_id": conversation_id,
            "next_step": {
                "node_id": next_node_id,
                "level": 1,
                "question": next_question
            },
            "flow": flow.flow,
            "history": history.history
        })

    flow = ConversationFlow.objects.filter(conversation_id=conversation_id).first()
    history = ConversationHistory.objects.filter(conversation_id=conversation_id).first()

    if not flow or not history:
        return JsonResponse({"error": "Invalid conversation_id provided."}, status=400)

    current_step = flow.flow[-1]
    current_question = current_step["question"]
    current_node_id = current_step["node_id"]
    current_level = current_step["level"]

    if not user_response:
        return JsonResponse({"error": "Response required for existing conversation."}, status=400)

    history.history.append({
        "timestamp": timezone.now().isoformat(),
        "sender": "User",
        "message": user_response
    })

    validated_category = None

    if current_node_id == "level_1_industry":
        if validate_response_with_ai_level_1(current_question, user_response):
            validated_category = user_response
    elif current_node_id == "level_2_business_status":
        valid_categories = list(FLOW_DEFINITION[current_node_id].keys())
        validated_category = classify_response_with_ai_level_2(current_question, user_response, valid_categories)
    elif current_node_id in ["level_2_positive"]:
        validated_category = classify_response_with_ai_level_2_positive(current_question, user_response)
    elif current_node_id in ["level_2_vague", "level_2_reject"]:
        validated_category = classify_response_with_ai_level_vague_reject(current_question, user_response)
    elif current_node_id in ["level_3_negative"]:
        validated_category = classify_response_with_ai_level_3(current_question, user_response)
    elif current_node_id in ["level_4_tell_more_good", "level_4_tell_more_bad", "level_4_tell_more_ok"]:
        validated_category = classify_response_with_ai_level_4(current_question, user_response)
    elif current_node_id in ["level_4_deal_with"]:    
        validated_category = classify_response_with_ai_level_4_deal_with(current_question, user_response)
    elif current_node_id == "level_5_you_must_be_top":
        validated_category = classify_response_with_ai_level_5_you_must_be_top(current_question, user_response)
    elif current_node_id == "level_5_glad_to_hear":
        validated_category = classify_response_with_ai_level_5_glad_to_hear(current_question, user_response)
    elif current_node_id == "level_6_best_of_luck":
        validated_category = classify_response_with_ai_level_6_best_of_luck(current_question, user_response)
    else:
        return JsonResponse({"error": "Unexpected conversation step."}, status=400)

    if not validated_category:
        error_message = "Your response didn't clearly answer my question."
        repeat_question = f"Sorry, {error_message} {current_question}"
        history.history.append({
            "timestamp": timezone.now().isoformat(),
            "sender": "AI",
            "message": repeat_question
        })
        history.updated_at = timezone.now()
        history.save()
        return JsonResponse({
            "conversation_id": conversation_id,
            "next_step": {
                "node_id": current_node_id,
                "level": current_level,
                "question": repeat_question
            },
            "flow": flow.flow,
            "history": history.history,
            "error": error_message
        })

    current_step["response"] = validated_category
    current_step["original_user_response"] = user_response
    current_step["validated"] = True
    flow.updated_at = timezone.now()

    next_node_id = get_next_step(flow)
    # Check if the next node is a final action
    final_action_result = execute_final_node_action(next_node_id, conversation_id, user_response)
    if final_action_result:
        return JsonResponse(final_action_result)

    original_question = QUESTION_TEXT_MAPPING.get(next_node_id, "Could you elaborate more?")
    next_question = get_varied_question(original_question,conversation_id)
    next_level = current_level + 1

    history.history.append({
        "timestamp": timezone.now().isoformat(),
        "sender": "AI",
        "message": next_question
    })

    flow.flow.append({
        "step": len(flow.flow) + 1,
        "level": next_level,
        "node_id": next_node_id,
        "question": original_question,
        "original_user_response": None,
        "response": None,
        "validated": False
    })

    # Atualiza no banco de dados
    flow.save()
    history.updated_at = timezone.now()
    history.save()

    return JsonResponse({
        "conversation_id": conversation_id,
        "next_step": {
            "node_id": next_node_id,
            "level": next_level,
            "question": next_question
        },
        "flow": flow.flow,
        "history": history.history
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
        "flow": conversation.flow,
        "error": error_message
    })