"""
Tool: Base de Conocimiento (RAG con Pinecone)
Permite buscar información en la base de conocimientos de DATAPATH.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
from dotenv import load_dotenv, find_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_core.tools import tool
from langchain_pinecone import PineconeVectorStore

load_dotenv(find_dotenv())

# ============================================
# CONFIGURACIÓN DE PINECONE
# ============================================
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "langchain-pinecone-asistente-de-ventas")

if not PINECONE_API_KEY:
    raise ValueError(
        "❌ Falta variable PINECONE_API_KEY en .env"
    )

embedding_model = OpenAIEmbeddings(model="text-embedding-ada-002")

# Conectar al índice existente de Pinecone
vectorstore = PineconeVectorStore(
    index_name=INDEX_NAME,
    embedding=embedding_model,
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
