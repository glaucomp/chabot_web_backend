from .base_agent import BaseAgent

class WorkshopAgent(BaseAgent):
    def __init__(self, openai_key, chroma_dir):
        super().__init__(openai_key, "workshop_tactics", chroma_dir)