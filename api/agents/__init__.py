from .brand_agent import BrandAgent
from .storyteller_agent import StorytellerAgent
from .team_agent import TeamAgent
from .idea_agent import IdeaAgent
from .strategy_agent import StrategyAgent
from .workshop_agent import WorkshopAgent
from .innovation_agent import InnovationAgent
from .max_agent import MaxAgent

def get_specialist_agent(topic, openai_key, chroma_dir):
    specialists = {
        "Brand tactics": BrandAgent,
        "Storyteller tactics": StorytellerAgent,
        "Team tactics": TeamAgent,
        "Idea tactics": IdeaAgent,
        "Strategy tactics": StrategyAgent,
        "Workshop tactics": WorkshopAgent,
        "Innovation tactics": InnovationAgent,
        "Max": MaxAgent,
    }

    agent_class = specialists.get(topic)
    if agent_class:
        return agent_class(openai_key, chroma_dir)
    else:
        raise ValueError(f"No specialist agent found for topic '{topic}'")