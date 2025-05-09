from .base_agent import BaseAgent

class IdeaAgent(BaseAgent):
    def __init__(self, openai_key, chroma_dir):
        super().__init__(openai_key, "idea_tactics", chroma_dir)