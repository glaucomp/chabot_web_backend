from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse

import logging
import time
import base64
import requests

from api.chatbot import (
    chatbot,    
)

from api.app.conversation import (
    prompt_conversation_site,
    prompt_conversation_admin,
    prompt_conversation_agent_ai,
    prompt_conversation_grok_admin,
    prompt_conversation_image,
    
 )

from api.app.max_conversation import (
   max_phone_conversation,
 )


from ..serializers import (
    PromptConversationAdminSerializer,
    PromptConversationAgentAiSerializer,
)

from ai_config.ai_constants import (
    LANGUAGE_DEFAULT,
)


from api.utils import (
  handle_html
)
from api.app.mongo import MongoDB

logger = logging.getLogger(__name__)

class RenderGeneratedHTMLView(APIView):
    def get(self, request, conversation_id):
        user_response = request.GET.get("last_response", "")  # se quiser passar via GET
        html_content = handle_html(conversation_id, user_response)
        return HttpResponse(html_content, content_type="text/html")
    
class PromptConversationMaxView(APIView):
    def post(self, request):
        logger.info("Starting prompt_conversation_site request")
        try:
            language_code = request.GET.get("language", LANGUAGE_DEFAULT)
            logger.info(f"Processing request for language: {language_code}")

            input_serializer = PromptConversationAdminSerializer(data=request.data)
            if not input_serializer.is_valid():
                logger.error(f"Validation failed: {input_serializer.errors}")
                return Response(
                    {"error": "Invalid input data", "details": input_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validated_data = input_serializer.validated_data

            response = max_phone_conversation(
                user_prompt=validated_data["prompt"],
                conversation_id=validated_data["conversation_id"],
            )

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error in prompt_conversation_site view: {str(e)}", exc_info=True
            )
            return Response(
                {"error": f"Request processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
class PromptConversationSiteView(APIView):
    def post(self, request):
        logger.info("Starting prompt_conversation_site request")
        try:
            language_code = request.GET.get("language", LANGUAGE_DEFAULT)
            logger.info(f"Processing request for language: {language_code}")

            input_serializer = PromptConversationAdminSerializer(data=request.data)
            if not input_serializer.is_valid():
                logger.error(f"Validation failed: {input_serializer.errors}")
                return Response(
                    {"error": "Invalid input data", "details": input_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validated_data = input_serializer.validated_data

            response = prompt_conversation_site(
                user_prompt=validated_data["prompt"],
                conversation_id=validated_data["conversation_id"],
            )

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error in prompt_conversation_site view: {str(e)}", exc_info=True
            )
            return Response(
                {"error": f"Request processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
class PromptConversationAdminView(APIView):
    def post(self, request):
        logger.info("Starting prompt_conversation_site request")
        try:
            language_code = request.GET.get("language", LANGUAGE_DEFAULT)
            logger.info(f"Processing request for language: {language_code}")

            input_serializer = PromptConversationAdminSerializer(data=request.data)
            if not input_serializer.is_valid():
                logger.error(f"Validation failed: {input_serializer.errors}")
                return Response(
                    {"error": "Invalid input data", "details": input_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            validated_data = input_serializer.validated_data

            response = prompt_conversation_admin(
                user_prompt=validated_data["prompt"],
                conversation_id=validated_data["conversation_id"],
            )

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error in prompt_conversation_site view: {str(e)}", exc_info=True
            )
            return Response(
                {"error": f"Request processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        try:
            conversation_id = request.query_params.get("conversation_id")
            if not conversation_id:
                return Response(
                    {"error": "conversation_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            db = MongoDB.get_db()
            conversation = db.conversations.find_one({"session_id": conversation_id})

            if not conversation:
                return Response(
                    {"error": "Conversation not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            response_data = {
                "conversation_id": conversation_id,
                "messages": conversation.get("messages", []),
                "translations": conversation.get("translations", []),
                "updated_at": conversation.get("updated_at"),
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve conversation history: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
class PromptConversationAgentAIView(APIView):
    def post(self, request):
        logger.info("Starting prompt_conversation_site request")

        try:
               # Validate input data
            input_serializer = PromptConversationAgentAiSerializer(data=request.data)
            if not input_serializer.is_valid():
                logger.error(f"Validation failed: {input_serializer.errors}")
                return Response(
                    {"error": "Invalid input data", "details": input_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Extract validated data
            prompt = input_serializer.validated_data["prompt"]
                     
            # Extract validated data
            validated_data = input_serializer.validated_data

            # Generate AI response
            # generation_start = time.time()
            logger.info("Starting AI response generation")

            response = prompt_conversation_agent_ai(
                user_prompt=validated_data["prompt"],
            )

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(
                f"Error in prompt_conversation_site view: {str(e)}", exc_info=True
            )
            return Response(
                {"error": f"Request processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request):
        db = None
        try:
            # Get conversation_id from query params
            conversation_id = request.query_params.get("conversation_id")
            if not conversation_id:
                return Response(
                    {"error": "conversation_id is required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Connect to MongoDB and get conversation history
            db = MongoDB.get_db()
            conversation = db.conversations.find_one({"session_id": conversation_id})

            if not conversation:
                return Response(
                    {"error": "Conversation not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # for our response data we have the updated_at
            response_data = {
                "conversation_id": conversation_id,
                "messages": conversation.get("messages", []),
                "translations": conversation.get("translations", []),
                "updated_at": conversation.get("updated_at"),
            }

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve conversation history: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        
class ConversationDetailView(APIView):
    def get(self, request, conversation_id):
        db = None
        start_time = time.time()
        try:
            db = MongoDB.get_db()
            
            conversation = db.conversations.find_one({"session_id": conversation_id})            
            if not conversation:
                return Response(
                    {"error": "Conversation not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Converte o ObjectId para string
            conversation["_id"] = str(conversation["_id"])
            
            return Response(conversation, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Error retrieving conversation: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class AllConversationsIdsView(APIView):
    def get(self, request):
        db = None
        try:
            db = MongoDB.get_db()
            sessions = list(db.conversations.find({}, {"session_id": 1, "_id": 0}))
            return Response(sessions, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Error retrieving session ids: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class PromptImageView(APIView):
    def post(self, request):
        try:
            conversation_id = request.data.get("conversation_id")
            image_base64 = request.data.get("image_base64")
            image_url = request.data.get("image_url")

            if not conversation_id:
                return Response(
                    {"error": "Missing conversation_id in request."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not image_base64 and not image_url:
                return Response(
                    {"error": "Provide either image_base64 or image_url."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if image_url:
                try:
                    img_response = requests.get(image_url)
                    if img_response.status_code != 200:
                        raise Exception(f"Failed to download image. Status {img_response.status_code}")
                    image_base64 = base64.b64encode(img_response.content).decode('utf-8')
                except Exception as download_error:
                    return Response(
                        {"error": f"Error downloading image: {str(download_error)}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            response = prompt_conversation_image(
                conversation_id=conversation_id,
                image_base64=image_base64
            )

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Error processing prompt_conversation_image: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )