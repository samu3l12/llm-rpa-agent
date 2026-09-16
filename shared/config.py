"""
Configuracion centralizada del proyecto.
Cargo las variables de entorno y preparo el LLM para que el resto
de modulos solo hagan 'from shared.config import llm' y listo.
Soporto dos proveedores: LM Studio (por defecto) y Gemini.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargo el .env desde la raiz del proyecto
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")

# Variables de configuracion
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "lmstudio")
FORM_URL = os.getenv("FORM_URL", "http://localhost:8080/index.html")
# _ Variable leída del .env (Normalmente invisible en producción)
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
CHROMA_DIR = os.getenv("CHROMA_DIR", str(_project_root / "rag" / "chroma_db"))

# Directorio de procedures
PROCEDURES_DIR = _project_root / "procedures"


def get_llm():
    """
    Instancio el LLM segun el proveedor configurado en .env.
    Lo hago dentro de una funcion para no cargar modulos innecesarios
    si no se va a usar uno de los proveedores.
    """
    if LLM_PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0,
        )

    # Por defecto: LM Studio (API compatible con OpenAI)
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        base_url=os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
        model=os.getenv("LMSTUDIO_MODEL", "google/gemma-4-26b-a4b"),
        api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
        temperature=0,
    )


# Singleton: lo importo una vez y lo uso en todo el proyecto
llm = get_llm()
