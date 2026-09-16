# Sistema RPA con Agente LLM

Sistema end-to-end donde un agente LLM orquesta automatizaciones RPA sobre formularios web. El usuario interactua en lenguaje natural y el agente decide que tools usar: buscar procedimientos, extraer parametros, ejecutar la automatizacion.

## Arquitectura

```
┌─────────────┐     ┌──────────┐     ┌──────────────────────┐
│  MAUI App   │────▶│ FastAPI  │────▶│  Agente LangGraph    │
│  (XAML)     │     │ :8000    │     │                      │
└─────────────┘     └──────────┘     │  ┌─────────────────┐ │
                                     │  │ search_procedures│─┼──▶ ChromaDB
┌─────────────┐                      │  │ extract_params   │─┼──▶ LLM
│  CLI app.py │─────────────────────▶│  │ run_workflow     │─┼──▶ Selenium
└─────────────┘                      │  │ list_procedures  │ │
                                     │  └─────────────────┘ │
┌─────────────┐                      └──────────────────────┘
│ Recorder.py │──▶ Workflows JSON ──▶ ChromaDB
└─────────────┘
```

## Eleccion LangGraph vs LangChain

He usado **LangGraph** (`create_react_agent`) en lugar de LangChain clasico por estas razones:

1. **Flujo con estados**: LangGraph gestiona el bucle ReAct como un grafo de nodos, lo que facilita añadir logica como confirmacion antes de ejecutar (human-in-the-loop con`interrupt_before`).
2. **Checkpointer nativo**: la memoria multi-turno viene integrada (InMemorySaver / SqliteSaver), sin tener que montar wrappers manuales.
3. **Escalabilidad**: si mañana necesito añadir nodos de validacion, bifurcaciones o pasos condicionales, LangGraph lo soporta de forma natural.
4. **API recomendada**: es la direccion actual del ecosistema LangChain.

## Requisitos

- Python 3.11+
- Chrome (para Selenium)
- LM Studio con un modelo que soporte tool calling (Gemma 4, Qwen 2.5, etc.)

## Instalacion

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar .env (ya viene preconfigurado para LM Studio)
# Edita .env si necesitas cambiar el proveedor LLM
```

## Uso

Se necesitan 3 terminales:

```bash
# Terminal 1: Servidor del formulario
python web_form/server.py

# Terminal 2: Indexar workflows (solo la primera vez)
python rag/index_procedures.py

# Terminal 3 (opcion A): CLI del agente
python agent/app.py

# Terminal 3 (opcion B): API para MAUI
uvicorn api.main:app --reload --port 8000
```

### Grabar un nuevo workflow

```bash
# Asegurate de que el servidor del formulario esta corriendo
python recorder/recorder.py
# Interactua con el formulario, luego pulsa ENTER
# Se genera el .workflow.json en procedures/
```

### Ejemplo de uso del agente

```
Tu: Dame de alta un producto: Camiseta Negra Roma, precio 19.99, stock 25, camisetas

  [TOOL] search_procedures({"query": "alta de producto"})
  [RESULTADO] [{"id": "alta_producto_v1", "titulo": "Alta de Producto", ...}]
  [TOOL] extract_parameters({"user_request": "...", "param_schema": "..."})
  [RESULTADO] {"nombre": "Camiseta Negra Roma", "precio": 19.99, ...}
  [TOOL] run_workflow({"procedure_id": "alta_producto_v1", "parameters": "..."})
  [RESULTADO] {"status": "ok", "duration_ms": 3200, ...}

Agente: He dado de alta el producto "Camiseta Negra Roma" correctamente.
        Precio: 19.99€, Stock: 25 unidades, Categoria: camisetas.
```

## Estructura del proyecto

```
web_form/           Formulario de producto + servidor HTTP
recorder/           Recorder Python con Selenium (inyeccion JS)
procedures/         Workflows JSON con placeholders
rag/                Indexacion en ChromaDB
agent/              Agente LangGraph + tools + runner RPA
api/                FastAPI backend
shared/             Config centralizada + templating
maui_app/           UI MAUI nativo (XAML + MVVM)
```
