import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer



logger = logging.getLogger(__name__)

class DocumentRepository:
    def __init__(self, 
                 server: str, 
                 collection_name: str, 
                 embedding_model_name: str):
        self.server = server
        self.collection_name = collection_name
        self.embedder = SentenceTransformer(embedding_model_name)
        self.embedding_dim = self.embedder.get_sentence_embedding_dimension()
        self.qdrant = None
        self.connected = False
        
        try:
            self.qdrant = QdrantClient(url=server)
            self.qdrant.get_collections()
            self.connected = True
            logger.info(f"✅ Connected to Qdrant at {server}")
            logger.info(f"Embedding dimension: {self.embedding_dim}")
            self._ensure_collection()
        except Exception as e:
            logger.warning(f"⚠️ Could not connect to Qdrant at {server}: {e}")
            logger.warning(f"⚠️ Qdrant features will be unavailable. Please start Qdrant:")
            logger.warning(f"docker run -p 6333:6333 qdrant/qdrant")
            self.qdrant = None
            self.connected = False
    
    def _ensure_collection(self):
        if not self.connected or not self.qdrant:
            logger.warning("Skipping collection creation - Qdrant not connected")
            return
        
        try:
            collections = [col.name for col in self.qdrant.get_collections().collections]
            if self.collection_name not in collections:
                logger.info(f"Creating collection: {self.collection_name}")
                self.qdrant.recreate_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=self.embedding_dim,
                        distance=models.Distance.COSINE
                    )
                )
                logger.info(f"✅ Collection created: {self.collection_name}")
            else:
                logger.info(f"✅ Collection already exists: {self.collection_name}")

        except Exception as e:
            logger.error(f"Error ensuring collection: {e}")
            self.connected = False
    
    def _embed_text(self, text: str) -> List[float]:
        return self.embedder.encode([text])[0].tolist()
    
    def add_document(self, 
                    text: str, 
                    metadata: Optional[Dict[str, Any]] = None,
                    doc_id: Optional[int] = None) -> int:
        try:
            embedding = self._embed_text(text)
            payload = {
                "text": text,
                "metadata": metadata or {}
            }
            
            self.qdrant.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=doc_id,
                        vector=embedding,
                        payload=payload
                    )
                ]
            )
            
            logger.info(f"Document added with ID: {doc_id}")
            return doc_id
        except Exception as e:
            logger.error(f"Error adding document: {e}")
            raise
    
    def search(self, 
              vector: List[float], 
              query: str = "",
              limit: int = 5) -> List[str]:

        if not self.connected or not self.qdrant:
            logger.warning(f"Search unavailable - Qdrant not connected. Please start Qdrant server.")
            return []
        
        try:
            logger.info(f"Searching for: {query}")
            
            search_result = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=None
            )
            
            results = []
            for hit in search_result:
                text = hit.payload.get("text", "")
                score = hit.score
                score_str = f"{score:.3f}" if score is not None else "N/A"
                logger.debug(f"Match (score: {score_str}): {text[:100]}...")
                results.append(text)
            
            logger.info(f"Found {len(results)} documents")
            return results
        
        except AttributeError:
            try:
                logger.info(f"Searching for: {query} (using search_points)")
                search_result = self.qdrant.search_points(
                    collection_name=self.collection_name,
                    query=vector,
                    limit=limit
                )
                
                results = []
                for hit in search_result.points:
                    text = hit.payload.get("text", "")
                    logger.debug(f"Match: {text[:100]}...")
                    results.append(text)
                
                logger.info(f"Found {len(results)} documents")
                return results
            
            except Exception as e2:
                logger.error(f"Error during search (both methods failed): {e2}")
                return []
            
        except Exception as e:
            logger.error(f"Error during search: {e}")
            return []
    
    def delete_document(self, doc_id: int) -> bool:
        try:
            self.qdrant.delete(
                collection_name=self.collection_name,
                points_selector=models.PointIdsList(
                    idxs=[doc_id]
                )
            )
            logger.info(f"Document deleted: {doc_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        try:
            info = self.qdrant.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "embedding_dim": self.embedding_dim
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {}
