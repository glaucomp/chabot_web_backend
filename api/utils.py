from .models import ConversationFlow , ConversationHistory
from django.utils import timezone
import openai

from api.services.chatbot import OPENAI_API_KEY
import logging
import random
from django.http import JsonResponse

from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage

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
    },
    "level_3_negative": {
        "POSITIVE": "level_4_deep_dive",
        "VAGUE": "level_3_tell_more",
        "REJECT": "level_3_encourage_deal"
    },
    "level_3_tell_more": {
        "NEXT": "level_4_deep_dive",
    },
    "level_3_encourage_deal": {
        "NEXT": "level_4_deep_dive",
    },
    "level_4_deep_dive": {
        "YES": "level_5_tried_solution",
        "NO": "level_4_guide_reflection",
    },
    "level_4_guide_reflection": {
        "NEXT": "level_5_tried_solution",
    },
    "level_5_tried_solution": { 
        "YES": "level_6_confirm_understanding",
        "NO": "level_6_confirm_understanding",
    },
    "level_5_encourage_optimism": {
        "NEXT": "level_6_confirm_understanding",
    },
    "level_6_confirm_understanding": {
        "NEXT": "level_7_solution",
    },
    "level_7_solution": {"END": True},
}

chat = ChatOpenAI(model_name="gpt-4o", temperature=0.8)


def get_varied_question(original_question, conversation_id):
    history = ConversationHistory.objects.filter(conversation_id=conversation_id).first()

    history_text = ""

    if history and history.history:
        history_text = "\n".join(
            f'{step["sender"]}: {step["message"]}'
            for step in history.history[-6:]
        )

        prompt = f"""
        You are a friendly assistant having a casual conversation like you're chatting with someone over coffee or on WhatsApp.
        Your goal is to rephrase the original question in a more casual and friendly way, as if you were chatting with a friend.
        Rewrite this question in a casual, friendly, and natural tone.

        You want to ask this question:
        "{original_question}"

        context of the conversation:
        {history_text}

        Guidelines:
        - Keep it short, simple, and human.
        - Use everyday, non-formal language.
        - Be warm and curious.
        - Avoid sounding robotic or overly formal.
        - Make it feel like a friendly chat.
        - Consult context of the conversation to make it more engaging.

        Return ONLY the rephrased question. No quotes, no extra text.
        """


        logger.info(f"[VARIED_QUESTION - Repetition] Prompt enviado:\n{prompt}")

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

        Provide ONLY your fully friendly rephrased sentence, no quotes, no extra text.
        Instructions:
        - Use a friendly and casual tone.
        - Avoid formal or technical language.
        - Make the question engaging and less robotic.
        - Show curiosity and enthusiasm about the user's business.
        """

        logger.info(f"[VARIED_QUESTION - Initial] Prompt enviado:\n{prompt}")

    response = chat([HumanMessage(content=prompt)])
    varied_question = response.content.strip()
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
    
    if next_node_data.get("END"):
        final_action_result = execute_final_node_action(next_node_id, conversation.conversation_id, user_response)
        if final_action_result:
            return JsonResponse(final_action_result)

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
        max_tokens=30,
        temperature=0
    )

    answer = response.choices[0].message.content.strip().upper()
    logger.info(f"[VALIDATE_RESPONSE] Validate response with AI Level 1: {answer}")
    return answer == "YES"

def classify_response_with_ai_level_2_positive(question, user_response):
    valid_categories = ["YES"]

    prompt = f"""
    You are categorizing a user's response about a specific issue mentioned in the original question.
    Original Question:
    "{question}"

    User's Response:
    "{user_response}"

    Instructions:
    - Respond strictly "YES" only if the user's response explicitly confirms or clearly indicates the issue.
    - Respond strictly "YES" only if the user's User's Response match with Original Question.

    Answer strictly and only with one word: "YES" if the user's response anything about them busines.

    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=30,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None


def classify_response_with_ai_level_2_vague_reject(question, user_response):
    valid_categories = ["NEXT"]
    prompt = f"""
        You are categorizing a user's response to the following question:
        Question:
        "{question}"
        User's response:
        "{user_response}"
        Instructions:
        - Respond ONLY with "NEXT" if the user's response clearly answer the question.
        """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
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
        max_tokens=50,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    logger.info(f"[CLASSIFY_RESPONSE] Classify response with AI Level 2: {category}")

    return category if category in valid_categories else None

def classify_response_with_ai_level_3(question, user_response):
    valid_categories = ["POSITIVE", "VAGUE", "REJECT"]

    prompt = f"""
    Categorize the user's response to the following question into exactly one of these categories: {', '.join(valid_categories)}.

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - Respond strictly "POSITIVE" if the user's response clearly and directly answers the question.
    - Respond strictly "VAGUE" if the user's response is unclear, ambiguous, or does not directly answer the question.
    - Respond strictly "REJECT" if the user's response explicitly indicates rejection or refusal to answer.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_3_tell_more(question, user_response):
    valid_categories = ["NEXT"]
    
    prompt = f"""
        Categorize the user's response to the following question clearly into one of these categories: NEXT or NONE.

        Question: "{question}"
        User's response: "{user_response}"

        Instructions:
        - Respond strictly "NEXT" if the user's response clearly provides specific details or elaborates further about the issue or problem mentioned.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_3_encourage_deal(question, user_response):
    valid_categories = ["NEXT"]

    prompt = f"""
        Categorize the user's response clearly into one of these two categories: NEXT or NONE.

        Question: "{question}"
        User's response: "{user_response}"

        Instructions:
        - Respond strictly "NEXT" if the user's response clearly provides specific details, explanations, or elaborates further about their company's issue or problem.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_4(question, user_response, conversation_id):
    
    history = ConversationHistory.objects.filter(conversation_id=conversation_id).first()

    history_text = ""

    if history and history.history:
        history_text = "\n".join(
            f'{step["sender"]}: {step["message"]}'
            for step in history.history[-6:]
        )

    valid_categories = ["YES", "NO"]
    
    prompt = f"""
    In that point you have to get more details, to undestand more the users problem, and give a clear answer to the user.
    Categorize the user's response to the following question clearly into one of these two categories: YES or NO.
    If the user clearly indicates a deep drive, in the conversation, answer ONLY "YES".
    If the user clearly indicates a negative, denial, or refusal to provide details, answer ONLY "NO".
    If the user's response is unclear or doesn't fit clearly, answer ONLY "None".
   

    Question: "{question}"
    User's response: "{user_response}"

    Context of the conversation:
    {history_text}

    Instructions:
    - If the user clearly indicates a positive, affirmative, or detailed response, answer ONLY "YES".
    - If the user clearly indicates a negative, denial, or refusal to provide details, answer ONLY "NO".
    - If the user's response is unclear or doesn't fit clearly, answer ONLY "None".
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_4_guide_reflection(question, user_response):
    valid_categories = ["NEXT"]
    prompt = f"""
    Categorize the user's response to the following question clearly into one of these two categories: NEXT or NONE.
    Question: "{question}"
    User's response: "{user_response}"
    Instructions:
    - Respond strictly "NEXT" if the user's response clearly provides specific details or elaborates further about the issue or problem mentioned.

    - Respond strictly "NONE" if the user's response does not provide any specific details or elaboration.

    """
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0
    )
    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_5_tried_solution(question, user_response):
    valid_categories = ["YES", "NO"]
    
    prompt = f"""
        Categorize the user's response clearly into one of these two categories: YES or NO.

        Question asked to user:
        "{question}"

        User's response:
        "{user_response}"

        Instructions:
        - Answer strictly "YES" if the user's response clearly answers your question directly, whether affirmatively or negatively (e.g., "Yes, I've tried" or "No, I haven't tried yet" are both clear answers).
        - Answer strictly "NO" if the user's response does NOT clearly answer your question, is ambiguous, unclear, irrelevant, or does not directly address the question.

        Respond ONLY with "YES" or "NO".
        """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_5_encourage_optimism(question, user_response):
    valid_categories = ["NEXT"]
    
    prompt = f"""
    Categorize the user's response to the following question clearly into one of these two categories: NEXT, NONE.

    Question: "{question}"
    User's response: "{user_response}"

    Instructions:
    - Respond strictly "NEXT" if the user's response clearly provides specific details or elaborates further about the issue or problem mentioned.
    - Respond strictly "NONE" if the user's response does not provide any specific details or elaboration.
    """

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_6_confirm_understanding(question, user_response, conversation_id):
    valid_categories = ["NEXT"]

    history = ConversationHistory.objects.filter(conversation_id=conversation_id).first()

    if history and history.history:
            history_text = "\n".join(
                f'{step["sender"]}: {step["message"]}'
                for step in history.history[-6:]
            )

    prompt = f"""
    You're a friendly assistant having a supportive conversation with a user. Your goal right now is:

    1. Carefully read the recent conversation provided below.
    2. Clearly summarize in a friendly, conversational, and supportive way the main points that the user has shared about their situation.
    3. Confirm explicitly with the user if your understanding is correct, asking politely if there's anything you missed or misunderstood.

    Conversation history:
    {history_text}

    Question asked to the user:
    "{question}"

    User's response to the question:
    "{user_response}"

    Instructions for your response:
    - Write a short, conversational, empathetic summary clearly showing you understand the user's current issues.
    - Explicitly ask the user to confirm if you understood everything correctly.
    - Invite them to clarify or add details if necessary, making it easy and comfortable for them to correct any misunderstanding.

    Respond ONLY with "NEXT" or "NONE".
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150,
        temperature=0.2
    )

    category = response.choices[0].message.content.strip().upper()
    return category if category in valid_categories else None

def classify_response_with_ai_level_7_solution(question, user_response, conversation_id):
    history = ConversationHistory.objects.filter(conversation_id=conversation_id).first()

    history_text = ""
    if history and history.history:
        history_text = "\n".join(
            f'{step["sender"]}: {step["message"]}'
            for step in history.history[-6:]
        )

    prompt = f"""
    You're a senior technology and business consultant providing high-tech solutions.

    Recent conversation context:
    {history_text}

    User's latest detailed input about their issue:
    "{user_response}"

    Instructions:
    Provide a highly professional, practical, and high-tech solution strictly based on the user's latest input and previous conversation context. 
    Your solution must:
    - Be clear, actionable, and directly relevant to the user's described situation.
    - Reflect current industry best practices and cutting-edge technologies.
    - Maintain a confident, supportive, and professional tone.

    Structured High-Tech Solution:
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=500
    )

    solution = response.choices[0].message.content.strip()
    return solution


def execute_final_node_action( conversation_id, user_response):
   return handle_html(conversation_id)
    
def handle_html(conversation_id, user_response):
    from .models import ConversationFlow, ConversationHistory

    # Load history
    history = ConversationHistory.objects.filter(conversation_id=conversation_id).first()
    history_text = ""
    if history and history.history:
        history_text = "\n".join(
            f'{step["sender"]} ({step["timestamp"]}): {step["message"]}'
            for step in history.history[-10:]
        )

    # Load flow
    flow = ConversationFlow.objects.filter(conversation_id=conversation_id).first()
    flow_text = ""
    if flow and flow.flow:
        flow_text = "\n".join(
            f'Step {step["step"]} (Level {step["level"]}) - Q: {step["question"]} | A: {step.get("response", "Awaiting response")}'
            for step in flow.flow
        )

    prompt = f"""
        You are a senior frontend engineer and business consultant.

        Your task is to generate a complete and professional standalone HTML document that displays a detailed overview of a conversation and its AI-generated solution.

        Context:
        - Conversation history:
        {history_text}

        - Conversation flow:
        {flow_text}


        Instructions:
        - Create a fully structured HTML5 document with <html>, <head>, <body>, etc.
        - Use clean, professional design with internal CSS (no frameworks).
        - Use modern fonts, soft shadows, good padding, and warm color palette.
        - Include the following sections in order:

        1. Header: "Report"
        2. Chat History: show messages in bubble-style layout with sender + timestamp.
        3. Conversation Flow: question + response per step.
        4. Next Step: show next planned question (if any).
        5. Solution Summary: formatted report, bullet points, yellow box.

        Rules:
        - Do not include explanations, comments, or Markdown formatting.
        - The output must be a clean, self-contained HTML page ready for display.

        Return ONLY the final HTML.
        """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1200
    )

    html = response.choices[0].message.content.strip()

    if not (html.startswith("<!DOCTYPE html>") or html.startswith("<html>")):
        html = f"<!DOCTYPE html>\n<html>\n{html}\n</html>"

    return html


def handle_html(conversation_id):
    from .models import ConversationFlow, ConversationHistory
    history_obj = ConversationHistory.objects.filter(conversation_id=conversation_id).first()
    history_text = ""
    if history_obj and history_obj.history:
        history_text = "\n".join(
            f'{h["sender"]} ({h["timestamp"]}): {h["message"]}'
            for h in history_obj.history[-10:]
        )

    # Load flow
    flow_obj = ConversationFlow.objects.filter(conversation_id=conversation_id).first()
    flow_text = ""
    solution_text = ""
    if flow_obj and flow_obj.flow:
        flow = flow_obj.flow
        flow_text = "\n".join(
            f'Step {step["step"]} (Level {step["level"]}) - Q: {step["question"]} | A: {step.get("response", "Awaiting response")}'
            for step in flow
        )
        # Try to extract a solution from the final step
        last_step = flow[-1]
        if last_step.get("node_id") == "level_7_solution":
            solution_text = last_step.get("response", "")

    return build_html_from_context(history_text, flow_text, solution_text)

def build_html_from_context(history_text, flow_text, solution_text=""):
    prompt = f"""
        You are a senior frontend engineer and business consultant.

        Your task is to generate a complete and professional standalone HTML document that displays a detailed overview of a conversation and its AI-generated solution.

        Context:
        - Conversation history:
        {history_text}

        - Conversation flow:
        {flow_text}

        - Final solution:
        {solution_text}

        Instructions:
        - Create a fully structured HTML5 document with <html>, <head>, <body>, etc.
        - Use clean, professional design with internal CSS (no frameworks).
        - Use modern fonts, soft shadows, good padding, and warm color palette.
        - Include the following sections in order:

        1. Header: "Report"
        2. Chat History: show messages in bubble-style layout with sender + timestamp.
        3. Conversation Flow: question + response per step.
        4. Solution Summary: formatted report, bullet points, yellow box.

        Rules:
        - Do not include explanations, comments, or Markdown formatting.
        - The output must be a clean, self-contained HTML page ready for display.
        """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1500
    )

    html = response.choices[0].message.content.strip()
    if not (html.startswith("<!DOCTYPE html>") or html.startswith("<html>")):
        html = f"<!DOCTYPE html>\n<html>\n{html}\n</html>"
    return html