from .base_agent import BaseAgent

class BrandAgent(BaseAgent):
    def __init__(self, openai_key, chroma_dir):
        super().__init__(openai_key, "brand_tactics", chroma_dir)