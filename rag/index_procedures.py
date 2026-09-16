"""
Indexo los workflows JSON en ChromaDB para que el agente pueda buscarlos
por similitud semantica. Cada workflow se convierte en un documento con
su titulo, descripcion y tags como texto, y los metadatos incluyen el id
y el param_schema.

Uso: python rag/index_procedures.py
"""

import json
import sys
from pathlib import Path

# Para poder importar shared
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from shared.config import CHROMA_DIR, PROCEDURES_DIR


def cargar_workflows(directorio: Path) -> list[dict]:
    """Leo todos los archivos .workflow.json del directorio."""
    workflows = []
    for archivo in sorted(directorio.glob("*.workflow.json")):
        contenido = archivo.read_text(encoding="utf-8")
        workflow = json.loads(contenido)
        workflows.append(workflow)
        print(f"  Cargado: {archivo.name} ({workflow.get('id', '?')})")
    return workflows


def workflow_a_documento(workflow: dict) -> Document:
    """
    Convierto un workflow en un Document de LangChain.
    El page_content es texto natural (titulo + descripcion + tags)
    porque es lo que usa el embedding para la busqueda semantica.
    Los metadatos llevan el id y el param_schema como JSON string.
    """
    titulo = workflow.get("titulo", "Sin titulo")
    descripcion = workflow.get("descripcion", "")
    tags = workflow.get("tags", [])

    # Texto semantico para el embedding
    texto = f"{titulo}. {descripcion} Tags: {', '.join(tags)}"

    # Metadatos que luego recupero junto con el documento
    metadata = {
        "id": workflow.get("id", ""),
        "titulo": titulo,
        "app": workflow.get("app", ""),
        "param_schema": json.dumps(workflow.get("param_schema", {}), ensure_ascii=False),
    }

    return Document(page_content=texto, metadata=metadata)


def main():
    print("=" * 60)
    print("INDEXACION DE WORKFLOWS EN CHROMADB")
    print("=" * 60)

    # Verifico que el directorio de procedures existe
    if not PROCEDURES_DIR.exists():
        print(f"Error: no existe el directorio {PROCEDURES_DIR}")
        sys.exit(1)

    # Cargo los workflows
    print(f"\nLeyendo workflows de: {PROCEDURES_DIR}")
    workflows = cargar_workflows(PROCEDURES_DIR)

    if not workflows:
        print("No se encontraron archivos .workflow.json")
        sys.exit(1)

    print(f"\nTotal workflows: {len(workflows)}")

    # Convierto a documentos de LangChain
    documentos = [workflow_a_documento(w) for w in workflows]

    # Preparo el modelo de embeddings (mismo que usa el profesor)
    print("\nCargando modelo de embeddings (all-MiniLM-L6-v2)...")
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Creo la base de datos vectorial en ChromaDB
    chroma_path = str(CHROMA_DIR)
    print(f"Indexando en ChromaDB: {chroma_path}")

    # Borro la coleccion anterior si existe para reindexar limpio
    vectorstore = Chroma.from_documents(
        documents=documentos,
        embedding=embedding_model,
        persist_directory=chroma_path,
        collection_name="procedures",
    )

    print(f"\nIndexados {len(documentos)} documentos correctamente")

    # Prueba rapida de busqueda
    print("\n-- Prueba de busqueda --")
    resultados = vectorstore.similarity_search_with_score(
        "dar de alta un producto", k=3
    )
    for i, (doc, score) in enumerate(resultados, 1):
        print(f"  {i}. [{score:.4f}] {doc.metadata.get('titulo', '?')}")

    print("\nIndexacion completada.")


if __name__ == "__main__":
    main()
