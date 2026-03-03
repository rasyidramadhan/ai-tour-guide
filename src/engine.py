import logging
import os
from src.loader import load_config
from typing import Tuple
from transformers import pipeline
from langchain_huggingface import HuggingFacePipeline
from langchain_core.prompts import PromptTemplate
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv



load_dotenv()
logger = logging.getLogger(__name__)

def initialize_models(llm_model_name: str) -> Tuple[HuggingFacePipeline, SentenceTransformer]:
    pipeline_kwargs = {
        "task": "text-generation",
        "model": llm_model_name,
        "max_length": load_config(["llm_config", "max_length"]),
        "temperature": load_config(["llm_config", "temperature"]),
        "top_p": load_config(["llm_config", "top_p"]),
        "repetition_penalty": load_config(["llm_config", "repetition_penalty"]),
    }
    
    text_pipeline = pipeline(**pipeline_kwargs)
    llm = HuggingFacePipeline(pipeline=text_pipeline)
    logger.info(f"✅ LLM model loaded") 
    
    embedding_model_name = os.getenv("EMBEDDING_MODEL")
    embedder = SentenceTransformer(embedding_model_name)
    logger.info(f"✅ Embedding model loaded")
    
    return llm, embedder

def create_prompt_template(system_prompt: str) -> PromptTemplate:
    template = f"""{system_prompt}

    Konteks dari dokumen:
    {{context}}

    Pertanyaan user: {{query}}

    Jawaban:"""
        
    return PromptTemplate.from_template(template)

class Embedding:
    def __init__(self, model_name: str = os.getenv("EMBEDDING_MODEL")):
        self.embedder = SentenceTransformer(model_name)

    def embed(self, text: str) -> list:
        embedding_vector = self.embedder.encode([text]).tolist()
        return embedding_vector[0] if embedding_vector else []
    
    def embed_batch(self, texts: list) -> list:
        embedding_vectors = self.embedder.encode(texts).tolist()
        return embedding_vectors
