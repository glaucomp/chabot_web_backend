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
    "level_1_industry": "What INDUSTRY are you in?",
    "level_2_business_status": "That's interesting, How is business going?",
    "level_2_positive": "Great happy for you. I have heard in your industry you guys have INDUSTRY ISSUE is that something you have to deal with?",
    "level_2_vague": "I’m not sure I fully understand. Could you clarify how things are currently going with your business?",
    "level_2_reject": "That’s absolutely fine! I’d be happy to assist. How’s your business doing at the moment?",
    "level_3_negative": "Alright, let’s discuss this together. What specifically would you like to improve, or what’s the main pain point?",

    "level_3_tell_more": "Tell me more about it...",
    "level_3_encourage_deal": "I have heard in your industry you guys have [INDUSTRY ISSUE] is that something you have to deal with?",
    "level_4_deep_dive": "I see.Ah, got it dealing with [INDUSTRY ISSUE] sounds challenging. Could you tell me a bit more about what is going on exactly? For example, which areas have you noticed being impacted the most?",
    "level_4_guide_reflection": "Uncertain about the next steps? I can help you with that. What are your thoughts on this?",
    "level_5_tried_solution":" I understand. Have you tried any solutions to address this issue? If so, what were they?",
    "level_5_encourage_optimism":"Come on, let’s get optimistic! What’s your outlook on this situation?",
    "level_6_confirm_understanding": "I think I got it. So, to summarize, you’re facing [INDUSTRY ISSUE] and you’ve tried [SOLUTION]. Is that correct?",
    
    "level_7_solution": "Can M&J intelligence help you with that? We have a solution that can help you with [INDUSTRY ISSUE]. Would you like to know more about it?",


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