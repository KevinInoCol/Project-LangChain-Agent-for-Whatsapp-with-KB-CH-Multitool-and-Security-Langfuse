"""
Tool: Base de Conocimiento (RAG con Qdrant)
Permite buscar información en la base de conocimientos de DATAPATH.

Consume una colección existente de Qdrant (self-hosted en DigitalOcean) vía
QDRANT_URL + QDRANT_API_KEY. La colección debe haberse creado con embeddings
de 1536 dimensiones (text-embedding-ada-002) y distancia coseno.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
from dotenv import load_dotenv, find_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool
from langchain_qdrant import QdrantVectorStore

load_dotenv(find_dotenv())

# ============================================
# CONFIGURACIÓN DE QDRANT
# ============================================
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "datapath")

if not QDRANT_URL:
    raise ValueError(
        "❌ Falta variable QDRANT_URL en .env "
        "(ej. https://tu-servidor-qdrant:6333)"
    )

embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")

# Conectar a la colección existente de Qdrant (hosteada en DigitalOcean).
# from_existing_collection valida que la colección exista y lee su configuración.
vectorstore = QdrantVectorStore.from_existing_collection(
    collection_name=COLLECTION_NAME,
    embedding=embedding_model,
    url=QDRANT_URL,
    api_key=QDRANT_API_KEY,
    prefer_grpc=False,   # REST (puerto 6333); usa True si expones gRPC (6334)
)


# ============================================
# FUNCIÓN INTERNA DE BÚSQUEDA
# ============================================
def buscar_en_base_conocimiento_interno(query: str, top_k: int = 5) -> str:
    """
    Función interna de búsqueda RAG con Pinecone.

    Args:
        query: Consulta de búsqueda
        top_k: Número de documentos a retornar

    Returns:
        str: Información encontrada formateada
    """
    try:
        docs = vectorstore.similarity_search(query, k=top_k)

        if not docs:
            return "No encontré información relevante en la base de conocimientos."

        contexto = "Información encontrada:\n\n"
        for i, doc in enumerate(docs, 1):
            contexto += f"[{i}]\n{doc.page_content}\n\n"

        return contexto

    except Exception as e:
        return f"Error al buscar: {str(e)}"


# ============================================
# TOOL EXPORTABLE
# ============================================
@tool
def buscar_datapath(consulta: str) -> str:
    """
    Busca información sobre DATAPATH en la base de conocimientos.
    Usa esta herramienta cuando el usuario pregunte sobre:
    - Programas de DATAPATH
    - Cursos y contenidos
    - Docentes e instructores
    - Precios y modalidades
    - Cualquier información relacionada con DATAPATH

    Args:
        consulta: La pregunta o tema a buscar
    """
    print(f"   🔍 Buscando: '{consulta}'")
    resultado = buscar_en_base_conocimiento_interno(consulta)
    return resultado
