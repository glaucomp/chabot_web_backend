
class InitialAgent:
    def __init__(self, topics):
        self.topics = topics
        self.openai_client = get_openai_client()

    def identify_topic(self, user_message):
        classification_prompt = f"""
        Classify the user's message into exactly ONE of these categories:

        {', '.join(self.topics)}

        User message: "{user_message}"

        Respond ONLY with the exact topic name.
        """

        response = self.openai_client.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You classify user messages strictly into predefined topics."},
                {"role": "user", "content": classification_prompt}
            ],
            temperature=0,
            max_tokens=10
        )

        chosen_topic = response.choices[0].message.content.strip()
        return chosen_topic

    def determine_next_action(self, chosen_topic, user_message):
        action_prompt = f"""
        Given the topic '{chosen_topic}' and user's message below, classify clearly whether the user wants to:

        1. Fix or improve something existing
        2. Create something completely new

        User message: "{user_message}"

        Respond with ONLY "fix" or "create".
        """

        response = self.openai_client.ChatCompletion.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "system", "content": "You classify user requests strictly into 'fix' or 'create'."},
                {"role": "user", "content": action_prompt}
            ],
            temperature=0,
            max_tokens=1
        )

        next_action = response.choices[0].message.content.strip().lower()
        return next_action
