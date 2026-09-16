"""
Servidor local para el formulario de alta de producto.
Uso: python web_form/server.py
Sirve en http://localhost:8080
"""
import http.server
import os
import sys

PORT = 8080
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        print(f"[WebForm] {args[0]}")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    with http.server.HTTPServer(("", port), Handler) as httpd:
        print(f"✔ Formulario disponible en http://localhost:{port}/index.html")
        print("  Pulsa Ctrl+C para detener el servidor.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✔ Servidor detenido.")


if __name__ == "__main__":
    main()
