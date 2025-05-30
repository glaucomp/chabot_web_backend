from openai import OpenAI
from api.services.brain import Brain
import os
import logging

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, openai_key, brain_collection, chroma_dir):
        self.client = OpenAI(api_key=openai_key)
        self.brain = Brain(brain_collection, chroma_dir)

        # Chame claramente o método para garantir o brain carregado
        self.ensure_brain_loaded(brain_collection)

    def ensure_brain_loaded(self, brain_collection):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
        file_name = f"{brain_collection}.markdown"
        file_path = os.path.join(base_dir, file_name)

        logger.info(f"Verificando o brain em: {file_path}")

        if self.brain._check_collection_count() == 0:
            logger.info(f"Brain '{brain_collection}' vazio. Carregando dados...")
            rules_chunks = self.brain._load_and_chunk_rules(file_path)
            all_docs = self.brain.prepare_brain_documents(rules_chunks)
            self.brain.vector_store.add_documents(all_docs)
            logger.info(f"{len(all_docs)} documentos carregados no brain '{brain_collection}'.")
        else:
            logger.info(f"Brain '{brain_collection}' has loaded before.")

    def provide_solution(self, user_message, action):
        docs = self.brain.query(user_message, k=3)
        context = "\n---\n".join([doc.page_content for doc in docs])

        prompt = f"""
        You are an expert assistant. The user wants to '{action}'. 
        Provide a concise and practical solution based on the context provided:

        Context:
        {context}

        User message:
        "{user_message}"
        """
        
        logger.info(f"@@@@@@@@@@@ '{prompt}' @@@@@@@@@@@@@@@.")

        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.5,
            max_tokens=400
        )

        return response.choices[0].message.content.strip()