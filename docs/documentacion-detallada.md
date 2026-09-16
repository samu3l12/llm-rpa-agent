# Documentación Académica y Técnica: Agente RPA + RAG con LangGraph

## 1. Introducción
El presente documento describe la arquitectura, los modelos y la guía de despliegue de un sistema avanzado de **Automatización Robótica de Procesos (RPA) Cognitivo**. El sistema es capaz de grabar flujos web mediante inyección dinámica de JavaScript, indexar esos flujos en una base de datos vectorial para su descubrimiento semántico (RAG), y ejecutar dichas tareas a petición del usuario interactuando mediante lenguaje natural.

La orquestación se realiza de forma autónoma gracias a un agente **ReAct** basado en **LangGraph**, y todo el sistema está interconectado con una interfaz gráfica desarrollada en **.NET MAUI**.

---

## 2. Modelos de Inteligencia Artificial Utilizados

El sistema emplea un enfoque dual, separando el modelo de lenguaje de propósito general del modelo de generación de embeddings, permitiendo una optimización máxima de recursos.

### 2.1. Modelo de Lenguaje Principal (LLM)
El núcleo de toma de decisiones del agente se configura en el archivo`shared/config.py`. El sistema está preparado para ser **agnóstico al proveedor**, soportando dos grandes vías:
*   **Ejecución Local y Privada (LM Studio):** Por defecto, el sistema se conecta a un servidor local compatible con OpenAI en el puerto`1234`. Está optimizado para modelos potentes capaces de realizar *Tool Calling*, como`google/gemma-4-26b-a4b` u otros modelos Llama 3 / Qwen.
*   **Ejecución en la Nube (Google Gemini):** Alternativamente, definiendo la variable`LLM_PROVIDER=gemini`, el agente levanta una instancia de`gemini-2.0-flash`.
*   **Rol del LLM:** El modelo operando a`temperature=0` se utiliza exclusivamente para analizar el *intent* del usuario, decidir qué herramienta invocar (Tool Calling), extraer los parámetros mediante JSON Schemas y formular la respuesta final.

### 2.2. Modelo de Embeddings (RAG)
Para la indexación semántica de los procedimientos, se ha optado por el modelo **`all-MiniLM-L6-v2`** de **HuggingFace**.
*   **Justificación Técnica:** Este modelo transforma textos en vectores densos de 384 dimensiones. Es extremadamente ligero y rápido, permitiendo ejecutarse directamente en la CPU del servidor local sin necesidad de costosas GPUs ni llamadas a APIs externas de pago (como OpenAI Embeddings).
*   **Uso:** Convierte el título y la descripción de los flujos grabados (archivos`.workflow.json`) en vectores matemáticos almacenados en **ChromaDB**. Cuando el usuario pide "registra una camiseta", el modelo vectoriza esa frase y calcula la similitud del coseno contra la base de datos, encontrando el procedimiento de "Alta de Producto" incluso si el usuario no usa las palabras exactas.

---

## 3. Arquitectura del Sistema

El proyecto está fuertemente desacoplado para asegurar la separación de responsabilidades:

1.  **Grabador de Flujos (`recorder/recorder.py`):** Utiliza Selenium para abrir el navegador e inyectar un *payload* JavaScript personalizado (`RECORDER_JS`). Este script captura eventos de usuario (`input`,`change`,`click`), los deduplica y los empaqueta en un Domain Specific Language (DSL). Los valores reales tecleados por el usuario se reemplazan por *placeholders* (ej.`{{precio}}`).
2.  **Motor RAG (`rag/index_procedures.py`):** Tarea de procesamiento en lote que escanea la carpeta`procedures/`, incrusta los JSON en ChromaDB y habilita el descubrimiento semántico para la Tool`search_procedures`.
3.  **Core del Agente (`agent/agent.py` y`agent/tools.py`):** Instanciado mediante **LangGraph**, creando un grafo cíclico ReAct (`create_react_agent`) inyectado con`InMemorySaver`. Esto proporciona al agente "memoria a corto plazo" (*Thread ID*), permitiéndole mantener un chat multi-turno si le faltan parámetros, y auto-corregirse si una tool falla.
4.  **Backend API (`api/main.py`):** Construida sobre **FastAPI**, expone las rutas RESTful. Utiliza Modelos de Datos estrictos en **Pydantic V2** (`ChatRequest`,`ChatResponse`) como contratos de datos que garantizan que el Frontend y el Backend se comunican de forma segura e inteligible.
5.  **Motor de Ejecución (`agent/runner.py`):** El`RPARunner` recibe el JSON hidratado y utiliza Selenium con`WebDriverWait` explícitos para interactuar físicamente con el DOM del formulario, garantizando solidez frente a retrasos de red.

---

## 4. Consolidación Tecnológica: LangChain vs LangGraph

Una de las decisiones arquitectónicas más críticas del proyecto es la utilización híbrida de ambas librerías, cada una enfocada en responsabilidades específicas. Esta unión se consolida principalmente en el archivo **`agent/agent.py`** y **`agent/tools.py`**.

### 4.1. El Rol de LangChain (Abstracciones y Primitivas)
LangChain se utiliza exclusivamente como la capa de integración de bajo nivel (las "piezas del lego"). Se delegan a LangChain las siguientes funciones:
*   **Abstracción del LLM:** Se usa`ChatOpenAI` y`ChatGoogleGenerativeAI` para tener una interfaz estándar sin importar si estamos usando LM Studio local o Gemini.
*   **Decoradores de Tools:** Las herramientas del agente en`agent/tools.py` se definen usando el decorador`@tool` de`langchain_core.tools`. Esto empaqueta automáticamente el *schema* de Python en el formato JSON que exige la API de OpenAI/Gemini.
*   **Sistema RAG:** La integración con ChromaDB y los modelos de HuggingFace (`HuggingFaceEmbeddings`) se realiza utilizando las clases nativas de`langchain_community`.

### 4.2. El Rol de LangGraph (Orquestación y Estado)
Mientras LangChain provee las piezas, **LangGraph** se utiliza como el "cerebro orquestador" que ensambla esas piezas en un flujo dinámico. Las *Chains* (cadenas lineales) de LangChain son insuficientes para un sistema RPA que puede fallar o necesitar múltiples pasos de razonamiento.
*   **Creación del Grafo:** En`agent/agent.py`, se invoca`create_react_agent()`, que por debajo construye un grafo de estado (`StateGraph`).
*   **Gestión del Estado:** A diferencia de las *Chains* que no recuerdan nada entre ejecuciones, LangGraph usa un objeto de estado intermedio. Si el Agente invoca la herramienta RAG, LangGraph guarda ese resultado en el estado y lo envía de vuelta al Agente en la siguiente iteración del grafo.
*   **Memoria (Checkpointing):** Se inyecta la clase`InMemorySaver()` en el compilador de LangGraph. Esto es lo que permite que el`thread_id` mantenga viva la conversación (multi-turno).

**Consolidación en código (`agent/agent.py`):**
```python
# Las tools provienen de LangChain
from agent.tools import search_procedures, run_workflow, extract_parameters

# El creador del agente y la memoria provienen de LangGraph
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import InMemorySaver

# LangGraph consume el LLM y las Tools de LangChain para crear el autómata de estados cíclico
tools = [search_procedures, extract_parameters, run_workflow]
agent = create_react_agent(llm, tools, checkpointer=InMemorySaver())
```
Esta sinergia permite beneficiarse del enorme ecosistema de integraciones de LangChain mientras se aprovecha la robustez matemática de los grafos dirigidos de LangGraph para la toma de decisiones.

---

## 5. Guía de Ejecución (Manual de Usuario / README)

El sistema requiere **Python 3.11**. Toda la instalación debe realizarse en un entorno virtual (`.venv`) para aislar dependencias como LangChain, PyTorch y Selenium.

### Opción A: Ejecución Integral mediante Interfaz Gráfica (Recomendada)
Para la presentación del proyecto y un uso de alto nivel:
1.  Abre el proyecto`maui_app` en **Visual Studio**.
2.  Inicia la aplicación (.NET MAUI Windows).
3.  Haz clic en el botón rojo **"🚀 Iniciar Servidores"** en la cabecera del chat. Esto lanzará automáticamente en segundo plano el servidor del Formulario (`web_form/server.py`) y la FastAPI (`uvicorn api.main:app`).
4.  La vista de "Procedimientos" se auto-actualizará dinámicamente conectando con la API, y el Chat mostrará el estado "Conectado a la API".
5.  Puedes activar el **Modo Debug** mediante el interruptor de la UI. Esto forzará al robot Selenium a operar de forma visible (*non-headless*) e insertará pausas de 1 segundo tras cada pulsación de tecla o clic para demostrar su funcionamiento en tiempo real.

### Opción B: Ejecución Modular por Terminal
Ideal para desarrollo, depuración o para grabar nuevos procedimientos:

1.  **Levantar el entorno de pruebas (Formulario):**
```powershell
    .\.venv\Scripts\activate
    python web_form/server.py
    ```
2.  **Grabar un nuevo Workflow:**
    Desde una nueva terminal, abre el grabador. *(Modifica previamente la variable "id" dentro del script`recorder.py` para darle nombre al proceso)*.
```powershell
    .\.venv\Scripts\activate
    python recorder/recorder.py
    ```
    Interactúa con el navegador web que se abre y pulsa`ENTER` en la consola para finalizar.
3.  **Indexar en RAG:**
    Para que el agente sea consciente del nuevo proceso grabado, debes ejecutar la indexación vectorial:
```powershell
    .\.venv\Scripts\activate
    python rag/index_procedures.py
    ```
4.  **Levantar la API Central:**
```powershell
    .\.venv\Scripts\activate
    python -m uvicorn api.main:app --host 127.0.0.1 --port 8500
    ```
5.  **Interactuar por Terminal (Alternativa a MAUI):**
    Si deseas comunicarte con el agente sin la interfaz de C#, puedes usar la CLI nativa que incluye impresión de trazas de pensamiento directas en consola:
```powershell
    .\.venv\Scripts\activate
    python agent/app.py
    ```
