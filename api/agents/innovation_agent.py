from .base_agent import BaseAgent

class InnovationAgent(BaseAgent):
    def __init__(self, openai_key, chroma_dir):
        super().__init__(openai_key, "innovation_tactics", chroma_dir)