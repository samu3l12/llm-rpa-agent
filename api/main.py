"""
FastAPI backend para comunicar la UI MAUI con el agente.
Expongo endpoints para chatear con el agente, listar procedimientos
y controlar el recorder.

Uso: uvicorn api.main:app --reload --port 8000
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from agent.agent import agent
from agent.tools import list_procedures as list_procedures_tool

app = FastAPI(
    title="RPA Agent API",
    description="API para interactuar con el agente de automatizacion RPA",
    version="1.0.0",
)

# Permito peticiones desde cualquier origen (para que MAUI pueda conectar)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Modelos de datos ──

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"
    debug_mode: bool = False # _ <-- El flag recibido desde C# (MAUI)


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict] = []


class ProcedureItem(BaseModel):
    id: str
    titulo: str
    descripcion: str
    parametros: list[str]


# ── Endpoints ──

@app.get("/health")
def health_check():
    """Verifico que la API esta funcionando."""
    return {"status": "ok", "message": "API del agente RPA funcionando"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Recibo un mensaje del usuario, se lo paso al agente y devuelvo
    la respuesta junto con las trazas de tools.
    """
    # _ La "mochila de configuración" que viaja por todo el grafo de LangGraph
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "debug_mode": request.debug_mode # _ <-- Inyectamos el flag aquí
        }
    }

    try:
        resultado = agent.invoke(
            {"messages": [HumanMessage(content=request.message)]},
            config=config,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error del agente: {str(e)}")

    # Extraigo la respuesta final
    respuesta = resultado["messages"][-1].content

    # Extraigo las trazas de tools para que la UI pueda mostrarlas
    trazas = []
    for msg in resultado.get("messages", []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                trazas.append({
                    "tool": tc["name"],
                    "args": tc["args"],
                })

    return ChatResponse(response=respuesta, tool_calls=trazas)


@app.get("/procedures")
def get_procedures():
    """Devuelvo la lista de procedimientos disponibles."""
    import json
    resultado = list_procedures_tool.invoke("")
    try:
        procedures = json.loads(resultado)
        return {"procedures": procedures}
    except Exception:
        return {"procedures": [], "raw": resultado}
