"""
Tool: Búsqueda en Internet (Tavily)
Permite buscar información actualizada en internet.

Autor: Ing. Kevin Inofuente Colque - DataPath
"""

import os
from dotenv import load_dotenv, find_dotenv
from langchain_core.tools import tool

load_dotenv(find_dotenv())

# ============================================
# CONFIGURACIÓN DE TAVILY
# ============================================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    raise ValueError(
        "❌ Falta TAVILY_API_KEY en .env\n"
        "Obtén tu API key gratis en: https://tavily.com"
    )

# Usar la nueva API de langchain-tavily
try:
    from langchain_tavily import TavilySearch
    tavily_search = TavilySearch(max_results=5)
except ImportError:
    # Fallback a la versión antigua si no está instalada
    from langchain_community.tools.tavily_search import TavilySearchResults
    tavily_search = TavilySearchResults(max_results=5)


# ============================================
# TOOL EXPORTABLE
# ============================================
@tool
def buscar_internet(consulta: str) -> str:
    """
    Busca información actualizada sobre DATAPATH en internet usando Tavily.
    Usa esta herramienta ÚNICAMENTE para complementar información sobre DATAPATH:
    - Reseñas o menciones de DATAPATH en medios
    - Comparación de DATAPATH con el mercado de formación en IA en Perú
    - Noticias recientes del sector de cursos de IA que ayuden a contextualizar DATAPATH
    - Información de DATAPATH que no esté en la base de conocimientos interna

    NUNCA uses esta herramienta para:
    - Preguntas de cultura general (política, deportes, noticias, ciencia)
    - Temas no relacionados con DATAPATH o formación en IA

    Args:
        consulta: El aspecto de DATAPATH o del sector de formación en IA a buscar
    """
    # Forzar que la búsqueda siempre esté en el contexto de DATAPATH
    consulta_datapath = f"DATAPATH escuela IA Peru {consulta}"
    print(f"   🌐 Buscando en internet: '{consulta_datapath}'")
    
    try:
        # Ejecutar búsqueda (siempre con contexto DATAPATH)
        resultados = tavily_search.invoke(consulta_datapath)
        
        if not resultados:
            return "No encontré información relevante en internet."
        
        # Formatear resultados
        respuesta = "Información encontrada en internet:\n\n"
        
        # Manejar diferentes formatos de respuesta
        if isinstance(resultados, list):
            for i, resultado in enumerate(resultados, 1):
                if isinstance(resultado, dict):
                    titulo = resultado.get("title", "Sin título")
                    contenido = resultado.get("content", "")
                    url = resultado.get("url", "")
                else:
                    titulo = f"Resultado {i}"
                    contenido = str(resultado)
                    url = ""
                
                respuesta += f"[{i}] {titulo}\n"
                respuesta += f"{contenido[:500]}...\n" if len(contenido) > 500 else f"{contenido}\n"
                if url:
                    respuesta += f"Fuente: {url}\n"
                respuesta += "\n"
        else:
            respuesta += str(resultados)
        
        return respuesta
        
    except Exception as e:
        return f"Error al buscar en internet: {str(e)}"
