from .base_agent import BaseAgent

class StorytellerAgent(BaseAgent):
    def __init__(self, openai_key, chroma_dir):
        super().__init__(openai_key, "storyteller_tactics", chroma_dir)