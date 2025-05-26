import json, uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import random

from .utils import (
    get_varied_question,
    get_next_step,
    validate_response_with_ai_level_1,
    classify_response_with_ai_level_2,
    classify_response_with_ai_level_2_positive,
    classify_response_with_ai_level_2_vague_reject,
    classify_response_with_ai_level_3,
    classify_response_with_ai_level_3_tell_more,
    classify_response_with_ai_level_3_encourage_deal,
    classify_response_with_ai_level_4,
    classify_response_with_ai_level_5_tried_solution,
    classify_response_with_ai_level_5_encourage_optimism,
    classify_response_with_ai_level_6_confirm_understanding,
    classify_response_with_ai_level_7_solution,
    execute_final_node_action,
    FLOW_DEFINITION,
)
from .models import ConversationFlow , ConversationHistory


QUESTION_TEXT_MAPPING = {
    "level_1_industry": "Hey! What industry are you in?",
    "level_2_business_status": "Nice! And how’s business going for you lately?",
    "level_2_positive": "Love hearing that! Have you ever had to deal with any challenges in your business?",
    "level_2_vague": "Hmm, I didn’t quite catch that. Can you tell me a bit more about how your business is doing?",
    "level_2_reject": "No worries at all! But if you're open to it, how are things going with your business?",
    "level_3_negative": "Gotcha. What’s the biggest challenge you're facing right now?",
    "level_3_tell_more": "Tell me more about that. What's really going on behind the scenes?",
    "level_3_encourage_deal": "I’ve heard [INDUSTRY ISSUE] can be a big challenge in your space. Is that something you’ve been dealing with too?",
    "level_4_deep_dive": "Sounds like [INDUSTRY ISSUE] isn’t easy to handle. What’s really going on? Any specific areas getting hit the hardest?",
    "level_4_guide_reflection": "Not sure what to do next? Maybe we can figure it out together. What are your thoughts so far?",
    "level_5_tried_solution": "Makes sense. Have you tried anything to fix it yet? What helped or didn’t?",
    "level_5_encourage_optimism": "Let’s keep a positive outlook! How are you feeling about all this?",
    "level_6_confirm_understanding": "Alright, just checking — you’re dealing with [INDUSTRY ISSUE] and you’ve tried [SOLUTION], right?",
    "level_7_solution": "Think M&J Intelligence could help with that? We’ve got some good options for [INDUSTRY ISSUE]. Want to hear more?",
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
        validated_category = classify_response_with_ai_level_2_vague_reject(current_question, user_response)
    elif current_node_id in ["level_3_negative"]:
        validated_category = classify_response_with_ai_level_3(current_question, user_response)
    elif current_node_id in ["level_3_tell_more"]:
        validated_category = classify_response_with_ai_level_3_tell_more(current_question, user_response)
    elif current_node_id in ["level_3_encourage_deal"]:    
        validated_category = classify_response_with_ai_level_3_encourage_deal(current_question, user_response)
    elif current_node_id in ["level_4_deep_dive"]:
        validated_category = classify_response_with_ai_level_4(current_question, user_response, conversation_id)
    elif current_node_id == "level_5_tried_solution":
        validated_category = classify_response_with_ai_level_5_tried_solution(current_question, user_response)
    elif current_node_id == "level_5_encourage_optimism":
        validated_category = classify_response_with_ai_level_5_encourage_optimism(current_question, user_response)
    elif current_node_id == "level_6_confirm_understanding":
        validated_category = classify_response_with_ai_level_6_confirm_understanding(current_question, user_response, conversation_id)
    elif current_node_id == "level_7_solution":
        validated_category = classify_response_with_ai_level_7_solution(current_question, user_response, conversation_id)
    
        flow.flow.append({
            "step": len(flow.flow),
            "level": current_level,
            "node_id": current_node_id,
            "question": current_question,
            "original_user_response": user_response,
            "response": "SOLUTION_PROVIDED",
            "validated": True,
            "timestamp": timezone.now().isoformat()
        })
        flow.updated_at = timezone.now()
        flow.save()

        history.history.append({
            "timestamp": timezone.now().isoformat(),
            "sender": "User",
            "message": user_response
        })
        history.history.append({
            "timestamp": timezone.now().isoformat(),
            "sender": "AI",
            "message": validated_category
        })
        history.updated_at = timezone.now()
        history.save()
        
        return JsonResponse({
            "solution": validated_category,
            "conversation_id": conversation_id,
            "flow": flow.flow,
            "history": history.history,
        })
    
    
    else:
        return JsonResponse({"error": "Unexpected conversation step."}, status=400)

    if not validated_category:


        unclear_phrases = [
            "Oh, I didn't quite catch that.",
            "I’m not sure I understand.",
            "Could you clarify that for me?",
            "I’m not sure I follow you.",
            "I’m not quite sure what you mean.",
            "I’m not sure I understand your point.",
            "I’m not sure I get your point.",
            "I’m not sure I understand what you’re saying.",
            "I’m not sure I understand your response.",
            "I’m not quite sure what you mean by that.",
          
        ]
        unclear_phrases = random.choice(unclear_phrases)

        error_message = "Your response didn't clearly answer my question."
        repeat_question = get_varied_question(unclear_phrases+", "+current_question, conversation_id)
        # repeat_question = f"Sorry, {error_message} {repeat_question}"
        
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