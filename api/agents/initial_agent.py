from openai import OpenAI

class InitialAgent:
    def __init__(self, openai_key, topics):
        self.client = OpenAI(api_key=openai_key)
        self.topics = topics

    def identify_topic(self, user_message):
        classification_prompt = f"""
        Given the user's message, classify it into EXACTLY one of the following categories. 
        Respond ONLY with the exact category name from the provided list, without punctuation or additional text:

        {', '.join(self.topics)}, unclear

        User's message: "{user_message}"
        """

        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": classification_prompt}
            ],
            temperature=0.0,
            max_tokens=150
        )

        topic = response.choices[0].message.content.strip()

        # Garanta correspondência exata
        topic_cleaned = topic.lower().replace('.', '').replace(',', '').strip()
        matched_topics = [t.lower() for t in self.topics]

        if topic_cleaned in matched_topics:
            return self.topics[matched_topics.index(topic_cleaned)]

        return "unclear"

    def determine_next_action(self, chosen_topic: str, user_message: str) -> str:
        action_prompt = f"""
        Given the topic '{chosen_topic}' and user's message below, classify clearly whether the user wants to:

        1. Fix or improve something existing
        2. Create something completely new

        User message: "{user_message}"

        Respond with ONLY "fix" or "create".
        """

        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "Classify user requests strictly into 'fix' or 'create'."},
                {"role": "user", "content": action_prompt}
            ],
            temperature=0,
            max_tokens=1
        )

        action = response.choices[0].message.content.strip().lower()
        return action

    def ask_clarifying_question(self, user_message):
        prompt = f"""
          You're a friendly, conversational assistant helping clarify user intent.

          User's message: "{user_message}"

          Internally, you're checking if the user's intent matches exactly one of these areas:
          {', '.join(self.topics)}

          Guidelines:
          - Do NOT use the word 'tactics'.
          - Casually reference or hint at these areas without explicitly listing them all at once.
          - Keep your clarifying question short, friendly, conversational, and relevant to the user's message.
          - Don't use the same words in the response as in the user's message.


          Respond only with your clarifying question.
        """

        response = self.client.chat.completions.create(
              model="gpt-4-turbo",
              messages=[{"role": "system", "content": prompt}],
              temperature=0.7,
              max_tokens=60
          )

        return response.choices[0].message.content.strip()