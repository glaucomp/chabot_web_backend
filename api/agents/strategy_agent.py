from .base_agent import BaseAgent

class StrategyAgent(BaseAgent):
    def __init__(self, openai_key, chroma_dir):
        super().__init__(openai_key, "strategy_tactics", chroma_dir)