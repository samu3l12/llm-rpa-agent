"""
Definicion de las tools del agente.
Cada tool tiene su docstring (lo lee el LLM para decidir cuando usarla)
y su schema de argumentos tipado (decorador @tool con type hints).

Tengo 4 tools:
- search_procedures: busca workflows por similitud semantica en ChromaDB
- extract_parameters: extrae los parametros de la peticion del usuario
- run_workflow: ejecuta un workflow RPA sobre el formulario
- list_procedures: lista todos los workflows disponibles
"""

import json
import sys
from pathlib import Path

# Para poder importar shared
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.tools import tool
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.runnables import RunnableConfig

from shared.config import llm, CHROMA_DIR, PROCEDURES_DIR, HEADLESS, FORM_URL
from shared.templating import render_workflow
from agent.runner import RPARunner

# Cargo el vectorstore una sola vez al importar el modulo
# _ Patrón Singleton para optimizar memoria
_embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2" # _ Modelo ligero de 384 dimensiones
)

_vectorstore = Chroma(
    persist_directory=str(CHROMA_DIR),
    embedding_function=_embedding_model,
    collection_name="procedures",
)


def _cargar_workflow(procedure_id: str) -> dict | None:
    """Busco y cargo un workflow por su id en el directorio de procedures."""
    for archivo in PROCEDURES_DIR.glob("*.workflow.json"):
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
        if contenido.get("id") == procedure_id:
            return contenido
    return None


@tool
def search_procedures(query: str) -> str:
    # _ Este docstring es importantísimo porque es el contrato que lee el LLM
    """Busca procedimientos de automatizacion por similitud semantica.
    Recibe una consulta en lenguaje natural y devuelve los procedimientos
    mas relevantes con su id, titulo, puntuacion de similitud y los
    parametros que necesita cada uno.
    Usarla SIEMPRE que el usuario pida ejecutar algun procedimiento o
    pregunte que automatizaciones hay disponibles para su peticion."""

    # _ Vectoriza la consulta y busca los 3 procedimientos más relevantes
    resultados = _vectorstore.similarity_search_with_score(query, k=3)

    if not resultados:
        return "No se encontraron procedimientos relevantes para esa consulta."

    salida = []
    for doc, score in resultados:
        info = {
            "id": doc.metadata.get("id", ""),
            "titulo": doc.metadata.get("titulo", ""),
            "score": round(score, 4),
            "param_schema": json.loads(doc.metadata.get("param_schema", "{}")),
        }
        salida.append(info)

    return json.dumps(salida, ensure_ascii=False, indent=2)


@tool
def extract_parameters(user_request: str, param_schema: str) -> str:
    """Extrae los parametros de la peticion del usuario segun el schema dado.
    Recibe la peticion original del usuario y el param_schema del procedimiento
    elegido (como JSON string). Devuelve un JSON con los valores extraidos.
    Si algun parametro no se encuentra en la peticion, lo pone como null.
    Usarla despues de elegir un procedimiento para sacar los datos concretos."""

    prompt = (
        "Extrae los parametros de la siguiente peticion del usuario.\n"
        "Devuelve SOLO un JSON valido (sin markdown, sin texto adicional) "
        "con las claves del schema y sus valores.\n"
        "Si un parametro no aparece en la peticion, pon null.\n\n"
        f"Schema de parametros:\n{param_schema}\n\n"
        f"Peticion del usuario:\n{user_request}\n\n"
        "JSON con los parametros:"
    )

    respuesta = llm.invoke(prompt)
    texto = respuesta.content.strip()

    # Limpio posibles fences de markdown que pueda meter el LLM
    # _ Limpieza manual de los backticks de markdown (```json)
    if texto.startswith("```"):
        lineas = texto.split("\n")
        # Quito la primera linea (```json) y la ultima (```)
        lineas = [l for l in lineas if not l.strip().startswith("```")]
        texto = "\n".join(lineas).strip()

    # Intento parsear el JSON
    try:
        params = json.loads(texto)
        return json.dumps(params, ensure_ascii=False)
    except json.JSONDecodeError:
        return json.dumps({
            "error": "No pude parsear la respuesta como JSON",
            "raw": texto
        })


@tool
def run_workflow(procedure_id: str, parameters: str, config: RunnableConfig) -> str:
    """Ejecuta un procedimiento RPA sobre el formulario web.
    Recibe el id del procedimiento y los parametros como JSON string.
    Abre el navegador, rellena el formulario automaticamente y devuelve
    el resultado de la ejecucion (ok/error, duracion, ultimo texto visible).
    Usarla cuando ya se tengan el id del procedimiento y todos los parametros."""

    # Cargo el workflow original
    workflow = _cargar_workflow(procedure_id)
    if not workflow:
        return json.dumps({
            "status": "error",
            "error_detail": f"No encuentro el workflow con id '{procedure_id}'"
        })

    # Parseo los parametros
    try:
        params = json.loads(parameters)
    except json.JSONDecodeError:
        return json.dumps({
            "status": "error",
            "error_detail": f"Los parametros no son JSON valido: {parameters}"
        })

    # Sustituyo los placeholders por los valores reales
    try:
        workflow_renderizado = render_workflow(workflow, params)
    except ValueError as e:
        return json.dumps({
            "status": "error",
            "error_detail": str(e)
        })

    # Sobreescribo la URL si hace falta (por si cambia el puerto)
    workflow_renderizado["url"] = FORM_URL

    # Leo config de debug
    # _ El 'debug_mode' nos llega inyectado automáticamente en 'configurable'
    debug_mode = config.get("configurable", {}).get("debug_mode", False)

    # Ejecuto el RPA
    # _ Sobreescribimos el headless del .env si el debug está activo en MAUI
    runner = RPARunner(headless=HEADLESS, timeout=10, debug_mode=debug_mode)
    resultado = runner.run(workflow_renderizado)

    return json.dumps(resultado, ensure_ascii=False)


@tool
def list_procedures() -> str:
    """Lista todos los procedimientos de automatizacion disponibles.
    Devuelve el id, titulo y descripcion corta de cada workflow indexado.
    Usarla cuando el usuario pregunte que procedimientos hay o cuando
    la peticion sea ambigua y necesite saber que opciones existen."""

    procedures = []
    for archivo in sorted(PROCEDURES_DIR.glob("*.workflow.json")):
        contenido = json.loads(archivo.read_text(encoding="utf-8"))
        procedures.append({
            "id": contenido.get("id", ""),
            "titulo": contenido.get("titulo", ""),
            "descripcion": contenido.get("descripcion", ""),
            "parametros": list(contenido.get("param_schema", {}).keys()),
        })

    if not procedures:
        return "No hay procedimientos indexados todavia."

    return json.dumps(procedures, ensure_ascii=False, indent=2)
