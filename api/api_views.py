import json, uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .utils import add_conversation_step, get_next_step, validate_response_with_ai
from .models import ConversationHistory

QUESTION_TEXT_MAPPING = {
    "level_1_industry": "What [INDUSTRY] are you in?",
    "level_2_business_status": "How is business going?",
    "level_3_good_industry_issue": "I've heard about some common [INDUSTRY ISSUE] in your field. Are you facing any of them?",
    "level_3_bad_improve": "Tell me more about what you'd like to improve.",
    "level_3_ok_share": "Is there something interesting happening you'd like to share?",
}

@csrf_exempt
def conversation_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "Only POST allowed"}, status=400)

    data = json.loads(request.body)
    conversation_id = data.get("conversation_id")
    user_response = data.get("response")

    if conversation_id:
        conversation = ConversationHistory.objects.filter(conversation_id=conversation_id).first()
        if not conversation:
            return JsonResponse({"error": "Invalid conversation_id provided."}, status=400)

        current_step = conversation.history[-1]
        current_question = current_step["question"]
        current_node_id = current_step["node_id"]
        current_level = current_step["level"]

        if user_response:
            # Valida a resposta usando OpenAI
            if not validate_response_with_ai(current_question, user_response):
                # NÃO cria novo passo no histórico. Apenas repete a pergunta atual.
                return JsonResponse({
                    "conversation_id": conversation_id,
                    "next_step": {
                        "node_id": current_node_id,
                        "level": current_level,
                        "question": f"Sorry, that didn't quite answer my question. {current_question}"
                    },
                    "history": conversation.history,
                    "error": "Your response didn't answer my question. Please try again."
                })

            # Atualiza resposta no passo atual (válida)
            current_step["response"] = user_response
            current_step["timestamp"] = timezone.now().isoformat()
            conversation.updated_at = timezone.now()
            conversation.save()

            # Segue para próximo passo somente após resposta válida
            next_node_id = get_next_step(conversation)
            next_question = QUESTION_TEXT_MAPPING.get(next_node_id, "Could you elaborate more?")
            next_level = current_level + 1

            # Salva imediatamente o próximo passo (após resposta válida)
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

        else:
            # Caso sem resposta (não deveria ocorrer)
            return JsonResponse({"error": "Response required for existing conversation."}, status=400)

    else:
        # Nova conversa já criando o primeiro passo no histórico
        conversation_id = str(uuid.uuid4())
        next_node_id = "level_1_industry"
        next_question = QUESTION_TEXT_MAPPING[next_node_id]

        conversation = ConversationHistory.objects.create(
            conversation_id=conversation_id,
            history=[
                {
                    "step": 1,
                    "level": 1,
                    "node_id": next_node_id,
                    "question": next_question,
                    "response": None,
                    "timestamp": None
                }
            ],
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