"""
Punto de entrada CLI del agente.
Este archivo NO contiene logica de orquestacion: solo construye el agente,
gestiona el bucle de entrada/salida y pasa cada turno al agente con el
mismo thread_id para mantener la conversacion.

Las trazas de tools se imprimen en consola para observabilidad.

Uso: python agent/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage
from agent.agent import agent


def imprimir_trazas(resultado):
    """
    Recorro los mensajes del resultado para mostrar las llamadas
    a tools que hizo el agente. Asi se ve que razona de verdad.
    """
    mensajes = resultado.get("messages", [])
    for msg in mensajes:
        # Los AIMessage con tool_calls son las decisiones del agente
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  [TOOL] {tc['name']}({tc['args']})")

        # Los ToolMessage son las respuestas de las tools
        if msg.type == "tool":
            contenido = msg.content
            # Trunco la salida si es muy larga
            if len(contenido) > 300:
                contenido = contenido[:300] + "..."
            print(f"  [RESULTADO] {contenido}")


def main():
    # Uso un thread_id fijo para toda la sesion
    config = {"configurable": {"thread_id": "chat-cli"}}

    print("=" * 60)
    print("  AGENTE RPA - Chat Interactivo")
    print("  Escribe tu peticion en lenguaje natural.")
    print("  Comandos: 'salir' para terminar")
    print("=" * 60)
    print()

    while True:
        try:
            pregunta = input("Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego!")
            break

        if not pregunta:
            continue

        if pregunta.lower() in {"salir", "exit", "quit"}:
            print("Hasta luego!")
            break

        # Invoco el agente con el mensaje del usuario
        # El mismo thread_id hace que recuerde la conversacion
        resultado = agent.invoke(
            {"messages": [HumanMessage(content=pregunta)]},
            config=config,
        )

        # Muestro las trazas de tools (observabilidad)
        imprimir_trazas(resultado)

        # Muestro la respuesta final del agente
        respuesta_final = resultado["messages"][-1].content
        print(f"\nAgente: {respuesta_final}\n")


if __name__ == "__main__":
    main()
