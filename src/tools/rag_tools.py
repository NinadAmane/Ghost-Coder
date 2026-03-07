import os
from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers import LanguageParser
from langchain_text_splitters import Language, RecursiveCharacterTextSplitter
from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
import logging

logger = logging.getLogger(__name__)

# Global variable to cache the vector store so we don't re-index on every search
_vector_store_cache = {}

def get_or_create_vector_store(repo_path: str) -> Chroma:
    """
    Indexes the repository and returns a Chroma vector store. Uses caching to prevent
    re-indexing multiple times during the same orchestration run.
    """
    if repo_path in _vector_store_cache:
        return _vector_store_cache[repo_path]
        
    logger.info(f"Indexing repository at {repo_path} for RAG search...")
    
    # We load source files. For simplicity, we just parse python files right now, 
    # but this can easily be expanded by removing the suffix filter or adding others.
    loader = GenericLoader.from_filesystem(
        repo_path,
        glob="**/*",
        suffixes=[".py", ".rs", ".js", ".ts", ".md"],
        exclude=["**/__pycache__", "**/.venv", "**/venv", "**/.git", "**/node_modules"],
        parser=LanguageParser()
    )
    docs = loader.load()
    
    # Use generic splitting logic for speed
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    
    # Local lightweight embeddings
    embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # In-memory transient ChromaDB instance
    vector_store = Chroma.from_documents(documents=splits, embedding=embedding_function)
    
    _vector_store_cache[repo_path] = vector_store
    logger.info(f"Indexed {len(splits)} chunks from {repo_path}.")
    return vector_store

@tool
def search_codebase(query: str, repo_path: str) -> str:
    """
    Semantically searches the entire codebase for a given query.
    Useful for finding implementations, usages, or logic related to the bug when you don't know the exact file name.
    
    Args:
        query: The natural language query to search the codebase for (e.g. "Where is the authentication payload parsed?")
        repo_path: The absolute path to the local repository.
    """
    try:
        if not os.path.exists(repo_path):
            return f"Error: Repository path {repo_path} does not exist."
            
        vector_store = get_or_create_vector_store(repo_path)
        retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        
        results = retriever.invoke(query)
        
        if not results:
            return "No matching source code found for the query."
            
        # Format the results
        formatted_results = []
        for doc in results:
            file_path = doc.metadata.get("source", "Unknown")
            # Create a localized relative path for clearer context
            rel_path = os.path.relpath(file_path, start=repo_path) if os.path.exists(file_path) else file_path
            
            content = doc.page_content
            formatted_results.append(f"--- File: {rel_path} ---\n{content}\n")
            
        return "\n".join(formatted_results)
    except Exception as e:
        logger.error(f"Error in search_codebase: {e}")
        return f"Error during search: {str(e)}"
