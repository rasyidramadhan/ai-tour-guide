import logging
import time
from typing import List, Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.prompts import PromptTemplate

from src.docs import DocumentRepository

logger = logging.getLogger(__name__)

class RAGState:
    def __init__(self):
        self.query: str = ""
        self.context: List[str] = []
        self.answer: str = ""
        self.embedding: List[float] = []

class RAG:
    def __init__(self, repo: DocumentRepository, embedder, llm):
        self.repo = repo
        self.embedder = embedder
        self.llm = llm
        self.system_prompt = self._load_system_prompt()
        self.chain = self._build_graph()
    
    def _load_system_prompt(self) -> str:
        try:
            with open("src/holiday.txt", "r", encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            logger.warning("System prompt file not found, using default")
            return "You are a helpful digital tour guide assistant."
    
    def _create_prompt_template(self) -> PromptTemplate:
        template = """Informasi dari database:
        {context}
        Pertanyaan: {query}
        Berdasarkan informasi di atas, berikan jawaban yang informatif dan singkat:"""
        
        return PromptTemplate.from_template(template)
    
    def _embed_query(self, text: str) -> List[float]:
        embedding = self.embedder.encode([text]).tolist()[0]
        return embedding
    
    def retrieve(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = state.get("query", "")
        top_k = state.get("top_k", 3)
        
        logger.info(f"Retrieving documents for query: {query}")
        embedding = self._embed_query(query)
        state["embedding"] = embedding
        results = self.repo.search(embedding, query, limit=top_k)
        
        logger.info(f"Retrieved {len(results)} documents")
        state["context"] = results
        
        return state
    
    def generate_answer(self, state: Dict[str, Any]) -> Dict[str, Any]:
        query = state.get("query", "")
        context = state.get("context", [])
        logger.info("Generating answer...")
    
        filtered_context = [item.strip() for item in context if item.strip() and len(item.strip()) > 10]
        context_text = "\n".join([f"- {item}" for item in filtered_context]) if filtered_context else "Tidak ada informasi terkait"
        
        prompt_template = self._create_prompt_template()
        prompt = prompt_template.format(context=context_text, query=query)
        
        try:
            response = self.llm.invoke(prompt)
            state["answer"] = response.strip()
        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            state["answer"] = "Maaf, terjadi kesalahan saat memproses permintaan Anda."
        
        return state
    
    def _build_graph(self) -> Any:
        workflow = StateGraph(dict)
        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("generate", self.generate_answer)
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        return workflow.compile()
    
    def process(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        start_time = time.time()
        
        logger.info(f"Processing query: {query}")
        
        result = self.chain.invoke({
            "query": query,
            "top_k": top_k,
            "context": [],
            "embedding": []
        })
        
        elapsed_time = time.time() - start_time
        logger.info(f"Query processed in {elapsed_time:.2f}s")
        
        return {
            "query": query,
            "answer": result.get("answer", ""),
            "context": result.get("context", []),
            "time execution": round(elapsed_time, 2)
        }
