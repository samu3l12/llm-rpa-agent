# Agente LLM que automatiza formularios web (RPA)

Sistema completo en el que un agente con modelo de lenguaje decide y ejecuta automatizaciones sobre formularios web. El usuario escribe en lenguaje natural y el agente busca el procedimiento adecuado, extrae los parámetros del mensaje y lanza la automatización.

```
Tú: Dame de alta el producto Camiseta Negra, precio 19.99, stock 25, categoría camisetas

  [TOOL] search_procedures  → encuentra "alta_producto_v1" en ChromaDB
  [TOOL] extract_parameters → {"nombre": "Camiseta Negra", "precio": 19.99, ...}
  [TOOL] run_workflow       → Selenium rellena y envía el formulario

Agente: He dado de alta el producto correctamente.
```

## Arquitectura

```
┌─────────────┐     ┌──────────┐     ┌────────────────────────┐
│  App MAUI   │────▶│ FastAPI  │────▶│  Agente LangGraph      │
│  o CLI      │     │          │     │  ┌──────────────────┐  │
└─────────────┘     └──────────┘     │  │ search_procedures│──┼──▶ ChromaDB
                                     │  │ extract_params   │──┼──▶ LLM
┌─────────────┐                      │  │ run_workflow     │──┼──▶ Selenium
│  Recorder   │──▶ workflows JSON ──▶│  └──────────────────┘  │
└─────────────┘                      └────────────────────────┘
```

## Piezas del sistema

| Carpeta | Qué hace |
|---|---|
| `recorder/` | Graba lo que haces en un formulario y genera un workflow en JSON, sin programar nada |
| `rag/` | Indexa esos procedimientos en ChromaDB para poder buscarlos por significado |
| `agent/` | Agente ReAct con LangGraph, sus herramientas y el ejecutor de Selenium |
| `api/` | Backend en FastAPI |
| `maui_app/` | Interfaz nativa en .NET MAUI (XAML + MVVM) |
| `web_form/` | Formulario de ejemplo con su servidor, para probar el sistema entero |
| `docs/` | Documentación técnica detallada del proyecto |

## Por qué LangGraph y no LangChain clásico

- El bucle ReAct se modela como un grafo, lo que permite meter una confirmación humana antes de ejecutar algo irreversible (`interrupt_before`).
- La memoria entre turnos viene integrada mediante *checkpointers*, sin montar envoltorios a mano.
- Añadir validaciones o bifurcaciones más adelante no obliga a rehacer el flujo.

## Cómo ejecutarlo

Requiere Python 3.11+, Chrome y un modelo con soporte de herramientas servido por LM Studio (o cualquier proveedor compatible con OpenAI).

```bash
pip install -r requirements.txt
cp .env.example .env          # configura aquí tu proveedor de LLM

python web_form/server.py      # terminal 1: formulario de prueba
python rag/index_procedures.py # terminal 2: indexar procedimientos (solo la 1ª vez)
python agent/app.py            # terminal 3: agente por consola
# o bien: uvicorn api.main:app --port 8000
```

## Tecnologías

LangGraph · LangChain · ChromaDB · Selenium · FastAPI · .NET MAUI · LM Studio
