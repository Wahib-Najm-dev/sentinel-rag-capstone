import os

from dotenv import load_dotenv

load_dotenv()


PROJECT_NAME = "SentinelRAG"
TOPIC = "SOC Operations and Cybersecurity Incident Response"
PROJECT_DESCRIPTION = (
    "An evidence-grounded RAG assistant for SOC analysts and incident response "
    "professionals, designed to retrieve authoritative cybersecurity guidance "
    "and generate answers grounded in verified source documents."
)
AUTHOR_NAME = "Wahib Najm Al-dain Al-Refaei"


# LLM configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "cohere")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
COHERE_MODEL = os.getenv("COHERE_MODEL", "command-r7b-12-2024")


# Reranker configuration
RERANKER_PROVIDER = os.getenv("RERANKER_PROVIDER", "cohere")
COHERE_RERANK_MODEL = os.getenv("COHERE_RERANK_MODEL", "rerank-v3.5")


# Authentication
APP_PASSWORD = os.getenv("APP_PASSWORD", "")


# Runtime configuration
TOKENIZERS_PARALLELISM = os.getenv("TOKENIZERS_PARALLELISM", "false")


# Retrieval configuration
VECTOR_TOP_K = 20
BM25_TOP_K = 20
TOP_N = 5


# Chunking configuration
CHUNK_SIZE_TOKENS = 350
CHUNK_OVERLAP_TOKENS = 60


# Embedding model
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"


# Paths
DATA_DIR = "data"
RAW_DATA_DIR = "data/raw"
INDEX_DIR = "data/index"
EVAL_DIR = "data/eval"