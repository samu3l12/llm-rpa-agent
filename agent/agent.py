"""
Construccion del agente con LangGraph.
Uso create_react_agent de langgraph.prebuilt, que es la forma moderna
de montar un agente ReAct con tool calling. El agente recibe la lista
de tools, un prompt de sistema y un checkpointer para memoria multi-turno.

Elijo LangGraph sobre LangChain clásico porque:
- Permite definir flujos con nodos y estados (escalable)
- Soporta interrupts para human-in-the-loop
- El checkpointer gestiona la memoria de forma transparente
- Es la API recomendada actualmente por LangChain
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver  # _ <-- Aporta estado cíclico y memoria

from shared.config import llm
from agent.tools import (  # _ <-- Aporta las primitivas y herramientas
    search_procedures,
    extract_parameters,
    run_workflow,
    list_procedures,
)

# Prompt de sistema que describe el rol del agente y sus reglas
SYSTEM_PROMPT = """\
Eres un asistente de automatizacion RPA. Tu trabajo es ayudar al usuario
a ejecutar procedimientos automatizados sobre formularios web.

Tienes estas herramientas:
- search_procedures: busca procedimientos por similitud semantica
- extract_parameters: extrae parametros de la peticion del usuario
- run_workflow: ejecuta un procedimiento RPA en el navegador
- list_procedures: lista todos los procedimientos disponibles

Reglas que debes seguir:
1. Cuando el usuario pida ejecutar algo, SIEMPRE busca primero el
   procedimiento adecuado con search_procedures.
2. Despues extrae los parametros con extract_parameters.
3. Si faltan parametros, pregunta al usuario antes de ejecutar.
4. Solo ejecuta run_workflow cuando tengas TODOS los parametros.
5. Si la peticion es ambigua, usa list_procedures para ver las opciones
   y pregunta al usuario cual quiere.
6. Si algo falla, explica el error de forma clara.
7. Responde siempre en espanol.
"""

# Lista de tools que el agente puede usar
tools = [search_procedures, extract_parameters, run_workflow, list_procedures]

# Checkpointer para memoria entre turnos (se mantiene en RAM)
checkpointer = InMemorySaver()


def crear_agente():
    """
    Creo el agente LangGraph con las tools y el checkpointer.
    Lo separo en funcion para poder reconstruirlo si hiciera falta.
    """
    # _ Punto de consolidación real de ambas tecnologías
    agente = create_react_agent(
        model=llm,                 # _ 1. El LLM (Pieza LangChain)
        tools=tools,               # _ 2. Las Herramientas (Pieza LangChain)
        prompt=SYSTEM_PROMPT,
        checkpointer=checkpointer, # _ 3. La Memoria (Pieza LangGraph)
    )
    return agente


# Creo el agente al importar el modulo (singleton)
agent = crear_agente()
