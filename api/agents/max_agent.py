from openai import OpenAI
from .brand_agent import BrandAgent
from .storyteller_agent import StorytellerAgent
from .team_agent import TeamAgent
from .idea_agent import IdeaAgent
from .strategy_agent import StrategyAgent
from .workshop_agent import WorkshopAgent
from .innovation_agent import InnovationAgent
from api.services.config import CHROMA_DIR
import logging

logger = logging.getLogger(__name__)

class MaxAgent:
    def __init__(self, openai_key):
        self.client = OpenAI(api_key=openai_key)

        self.agents = [
            BrandAgent(openai_key, CHROMA_DIR),
            StorytellerAgent(openai_key, CHROMA_DIR),
            TeamAgent(openai_key, CHROMA_DIR),
            IdeaAgent(openai_key, CHROMA_DIR),
            StrategyAgent(openai_key, CHROMA_DIR),
            WorkshopAgent(openai_key, CHROMA_DIR),
            InnovationAgent(openai_key, CHROMA_DIR)
        ]

    def gather_information(self, user_message, k=2):
        docs = []
        for agent in self.agents:
            docs += agent.brain.query(user_message, k=k)
        return docs

    def provide_human_like_response(self, user_message):
      docs = self.gather_information(user_message)

      combined_context = "\n---\n".join([doc.page_content for doc in docs])

      prompt = f"""
      You are Max, a friendly and informal consultant having a casual, brief phone conversation. 
      You quickly glanced at some notes from colleagues about branding, storytelling, team management, ideas, strategy, workshops, and innovation.

      Here is an example of the conversational style you should always use:

      Caller: "Hey Max, how are you?"
      Max: "Hey! I'm good, thanks! What's up?"

      Caller: "I need some quick ideas for our branding strategy."
      Max: "Got it! Maybe you could try quick behind-the-scenes videos to humanize your brand. Could be great!"

      Now, the real caller just asked: "{user_message}"

      Using the style above, reply casually, very briefly (maximum two short sentences), and always as if you're speaking naturally over the phone.
      
      combined_context: "{combined_context}"
      """

      try:
          response = self.client.chat.completions.create(
              model="gpt-4-turbo",
              messages=[{"role": "system", "content": prompt}],
              temperature=0.9,  # bem espontâneo
              max_tokens=50     # curta resposta (~1-2 frases curtas)
          )
          return response.choices[0].message.content.strip()

      except Exception as e:
          logger.error(f"Error generating MaxAgent response: {e}")
          return "Hey, sorry, line dropped! Could you say that again?"