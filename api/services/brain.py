import os
import logging
import chromadb
import json
import re
import tiktoken
import warnings

from typing import List
from dotenv import load_dotenv
from langchain_cohere import CohereEmbeddings
from langchain_community.vectorstores import Chroma
from api.ai_services import BrainDocument

warnings.filterwarnings("ignore", category=UserWarning, module="langchain")

from .config import COLLECTION_NAME, CHROMA_DIR
from ai_config.ai_constants import COHERE_MODEL

logger = logging.getLogger(__name__)
load_dotenv()


class Brain:
    _instances = {}

    def __new__(cls, collection_name=COLLECTION_NAME, chroma_dir=CHROMA_DIR):
        key = (collection_name, chroma_dir)
        if key not in cls._instances:
            cls._instances[key] = super(Brain, cls).__new__(cls)
        return cls._instances[key]

    def __init__(self, collection_name=COLLECTION_NAME, chroma_dir=CHROMA_DIR):
        if hasattr(self, 'initialized'):
            return

        self.collection_name = collection_name
        self.chroma_dir = chroma_dir
        self.embedding_model = CohereEmbeddings(model=COHERE_MODEL, user_agent="mjpro")
        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_model,
            persist_directory=self.chroma_dir,
        )
        self.ensure_documents_loaded()
        self.initialized = True

    def ensure_documents_loaded(self):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data"))
        file_name = f"{self.collection_name}.markdown"
        file_path = os.path.join(base_dir, file_name)

        if self._check_collection_count() == 0:
            rules_chunks = self._load_and_chunk_rules(file_path)
            all_docs = self.prepare_brain_documents(rules_chunks)

            if all_docs:
                self.vector_store.add_documents(all_docs)
                logger.info(f"{len(all_docs)} documents loaded into collection '{self.collection_name}'.")
            else:
                logger.warning(f"No documents found to load for '{self.collection_name}'.")
        else:
            logger.info(f"ChromaDB already initialized with documents for '{self.collection_name}'.")

    def _load_and_chunk_rules(self, file_path, max_tokens=400):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                rules_content = f.read()

            if not rules_content.strip():
                logger.error(f"❌ Arquivo {file_path} está vazio.")
                return []

            sections = re.split(r'(## .+)', rules_content)
            encoding = tiktoken.encoding_for_model("gpt-4")
            chunks, current_chunk, current_tokens = [], "", 0

            for section in sections:
                if not section.strip():
                    continue
                section_tokens = len(encoding.encode(section))
                if current_tokens + section_tokens > max_tokens:
                    chunks.append(current_chunk.strip())
                    current_chunk, current_tokens = section, section_tokens
                else:
                    current_chunk += "\n" + section
                    current_tokens += section_tokens

            if current_chunk:
                chunks.append(current_chunk.strip())

            return [{
                "id": f"{os.path.basename(file_path)}_chunk_{i}",
                "content": chunk,
                "metadata": {
                    "category": "static_rules",
                    "source": os.path.basename(file_path)
                }
            } for i, chunk in enumerate(chunks)]

        except Exception as e:
            logger.error(f"Error loading rules file {file_path}: {e}")
            return []


    def _load_and_chunk_rules_array(self, file_names=["default_cards.markdown", "innovation_tactics.markdown"], max_tokens=400):
        base_dir = os.path.join(os.path.dirname(__file__), "../../data")

        all_rules_content = ""

        try:
            for file_name in file_names:
                file_path = os.path.join(base_dir, file_name)
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()
                    all_rules_content += "\n" + file_content

            # Divide o conteúdo combinado por seções
            sections = re.split(r'(## .+)', all_rules_content)
            encoding = tiktoken.encoding_for_model("gpt-4")
            chunks, current_chunk, current_tokens = [], "", 0

            # Processa cada seção como antes
            for section in sections:
                if not section.strip():
                    continue
                section_tokens = len(encoding.encode(section))
                if current_tokens + section_tokens > max_tokens:
                    chunks.append(current_chunk.strip())
                    current_chunk, current_tokens = section, section_tokens
                else:
                    current_chunk += "\n" + section
                    current_tokens += section_tokens

            if current_chunk:
                chunks.append(current_chunk.strip())

            return [{
                "id": f"rules_{i}",
                "content": chunk,
                "metadata": {"category": "static_rules"}
            } for i, chunk in enumerate(chunks)]

        except Exception as e:
            logger.error(f"Error chunking rules files: {e}")
        return []

    def prepare_brain_documents(self, raw_docs):
        return [
            BrainDocument(id=doc["id"], page_content=doc["content"], metadata=doc["metadata"])
            for doc in raw_docs
        ]

    def _check_collection_count(self):
        client = chromadb.PersistentClient(path=self.chroma_dir)
        collection = client.get_or_create_collection(name=self.collection_name)
        return collection.count()

    def query(self, query: str, k: int = 3):
        return self.vector_store.similarity_search(query, k=k)
    

    '''
 def load_and_process_json_file(self) -> List[dict]:
        base_dir = os.path.join(os.path.dirname(__file__), "../../data")
        database_files = ["database_part_1.json", "database_part_2.json", "database_part_3.json", "database_part_4.json"]
        all_documents = []

        for file_name in database_files:
            file_path = os.path.join(base_dir, file_name)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        detailed_answer = item.get("answer", {}).get("detailed", {}).get("en", "")
                        if item.get("question", {}).get("text") and detailed_answer:
                            all_documents.append({
                                "id": item.get("id", "no_id"),
                                "content": f"Question: {item['question']['text']}\nAnswer: {detailed_answer}",
                                "metadata": {
                                    "category": ",".join(item.get("metadata", {}).get("category", [])),
                                    "subCategory": item.get("metadata", {}).get("subCategory", ""),
                                },
                            })
            except Exception as e:
                logger.error(f"Error loading {file_name}: {e}")
        return all_documents
'''