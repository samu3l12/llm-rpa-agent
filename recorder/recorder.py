"""
Recorder de workflows para RPA.
Abro un navegador con Selenium, inyecto JavaScript para capturar las
acciones del usuario y al terminar genero un workflow JSON con el formato
DSL que espera el runner.

Uso:
    1. Levantar el servidor: python web_form/server.py
    2. Ejecutar el recorder: python recorder/recorder.py
    3. Interactuar con el formulario en el navegador
    4. Pulsar ENTER en la terminal para parar la grabacion
    5. Se genera el archivo .workflow.json en procedures/
"""

from __future__ import annotations

import json
import platform
import threading
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# URL del formulario (se puede sobreescribir con variable de entorno)
import os
import sys

# Para poder importar shared.config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FORM_URL = os.getenv("FORM_URL", "http://localhost:8080/index.html")
POLL_INTERVAL = 0.75
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "procedures"

# Campos del formulario de producto y sus placeholders
FIELD_PLACEHOLDERS = {
    "nombre": "{{nombre}}",
    "precio": "{{precio}}",
    "stock": "{{stock}}",
    "categoria": "{{categoria}}",
}


# ══════════════════════════════════════════════════════════════
# JavaScript que se inyecta en el navegador
# ══════════════════════════════════════════════════════════════
# click, input y change y guardarlos en window.__rpaRecorder.actions.
# Desde Python los recojo con execute_script.

RECORDER_JS = r"""
(() => {
    if (window.__rpaRecorderInstalled) return;
    window.__rpaRecorderInstalled = true;

    function cssEsc(value) {
        if (window.CSS && CSS.escape) return CSS.escape(String(value));
        return String(value).replace(/([ #;?%&,.+*~':\"!^$\[\]()=>|\/])/g, '\\$1');
    }

    function getSelector(el) {
        if (!el || el.nodeType !== 1) return '';
        if (el.id) return '#' + cssEsc(el.id);
        if (el.name) return el.tagName.toLowerCase() + '[name="' + cssEsc(el.name) + '"]';

        // Fallback: construyo un path CSS
        var path = [];
        while (el && el.nodeType === 1 && el.tagName.toLowerCase() !== 'html') {
            var selector = el.tagName.toLowerCase();
            if (el.id) {
                path.unshift('#' + cssEsc(el.id));
                break;
            }
            if (el.name) {
                selector += '[name="' + cssEsc(el.name) + '"]';
                path.unshift(selector);
                break;
            }
            var parent = el.parentElement;
            if (parent) {
                var siblings = Array.from(parent.children).filter(function(c) {
                    return c.tagName === el.tagName;
                });
                if (siblings.length > 1) {
                    selector += ':nth-of-type(' + (siblings.indexOf(el) + 1) + ')';
                }
            }
            path.unshift(selector);
            el = parent;
        }
        return path.join(' > ');
    }

    function getLabelText(el) {
        if (!el) return '';
        if (el.id) {
            var lbl = document.querySelector('label[for="' + cssEsc(el.id) + '"]');
            if (lbl) return lbl.textContent.trim();
        }
        var wrapper = el.closest('label');
        if (wrapper) return wrapper.textContent.trim();
        return '';
    }

    window.__rpaRecorder = {
        actions: [],
        startedAt: new Date().toISOString()
    };

    function dedupe(action) {
        var actions = window.__rpaRecorder.actions;
        var last = actions[actions.length - 1];
        if (!last) return false;
        if (action.type === 'input' && last.type === 'input' && last.selector === action.selector) {
            last.value = action.value;
            return true;
        }
        return false;
    }

    function record(action) {
        action.timestamp = new Date().toISOString();
        if (!dedupe(action)) {
            window.__rpaRecorder.actions.push(action);
        }
    }

    // Capturo clicks solo en elementos interactivos que no sean inputs
    // (los inputs se capturan con los listeners de input/change)
    document.addEventListener('click', function(e) {
        var el = e.target.closest('button, a, [role="button"], input[type="button"], input[type="submit"]');
        if (!el) return;
        record({
            type: 'click',
            selector: getSelector(el),
            tag: el.tagName.toLowerCase(),
            text: (el.innerText || '').trim().slice(0, 80),
            fieldName: el.name || el.id || '',
            label: getLabelText(el)
        });
    }, true);

    // Capturo escritura en inputs y textareas
    document.addEventListener('input', function(e) {
        var el = e.target;
        if (!el) return;
        var tag = el.tagName.toLowerCase();
        if (tag !== 'input' && tag !== 'textarea') return;
        var inputType = (el.getAttribute('type') || '').toLowerCase();
        if (['checkbox', 'radio', 'button', 'submit'].indexOf(inputType) !== -1) return;

        record({
            type: 'input',
            selector: getSelector(el),
            tag: tag,
            inputType: inputType,
            value: el.value,
            fieldName: el.name || el.id || '',
            label: getLabelText(el)
        });
    }, true);

    // Capturo cambios en selects y checkboxes
    document.addEventListener('change', function(e) {
        var el = e.target;
        if (!el) return;
        var tag = el.tagName.toLowerCase();
        var inputType = (el.getAttribute('type') || '').toLowerCase();

        if (tag === 'select') {
            var selectedText = el.options && el.options[el.selectedIndex]
                ? el.options[el.selectedIndex].text : '';
            record({
                type: 'change',
                selector: getSelector(el),
                tag: tag,
                value: el.value,
                selectedText: selectedText,
                fieldName: el.name || el.id || '',
                label: getLabelText(el)
            });
            return;
        }

        if (inputType === 'checkbox' || inputType === 'radio') {
            record({
                type: 'change',
                selector: getSelector(el),
                tag: tag,
                inputType: inputType,
                value: String(el.checked),
                fieldName: el.name || el.id || '',
                label: getLabelText(el)
            });
        }
    }, true);

    // Capturo envios de formularios
    document.addEventListener('submit', function(e) {
        var form = e.target;
        if (!form) return;
        record({
            type: 'submit',
            selector: getSelector(form),
            tag: 'form',
            fieldName: form.name || form.id || ''
        });
    }, true);

    console.log('[Recorder] instalado correctamente');
})();
"""


def crear_driver():
    """Creo el navegador con Chrome y webdriver-manager."""
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    driver.set_window_size(1400, 900)
    return driver


def inyectar_recorder(driver):
    """Inyecto el JavaScript del recorder en la pagina."""
    driver.execute_script(RECORDER_JS)


def obtener_acciones(driver):
    """Recojo las acciones capturadas por el JS inyectado."""
    return driver.execute_script(
        "return (window.__rpaRecorder && window.__rpaRecorder.actions) "
        "? window.__rpaRecorder.actions : [];"
    )


def convertir_a_step_dsl(action):
    """
    Convierto una accion cruda del recorder JS al formato DSL
    que espera el runner (type, click, select, wait_for_text).
    """
    tipo = action.get("type", "")
    selector = action.get("selector", "")
    field_name = action.get("fieldName", "")
    tag = action.get("tag", "")
    value = action.get("value", "")

    # Determino el tipo de localizador
    if selector.startswith("#"):
        by = "id"
        by_value = selector[1:]  # quito el #
    elif "[name=" in selector:
        by = "name"
        by_value = selector.split('"')[1] if '"' in selector else selector
    else:
        by = "css"
        by_value = selector

    target = {"by": by, "value": by_value}

    # Sustituyo valores literales por placeholders si corresponde
    placeholder_value = value
    if field_name in FIELD_PLACEHOLDERS:
        placeholder_value = FIELD_PLACEHOLDERS[field_name]

    if tipo == "click":
        return {"type": "click", "target": target}

    if tipo == "input":
        return {"type": "type", "target": target, "value": placeholder_value}

    if tipo == "change" and tag == "select":
        return {"type": "select", "target": target, "value": placeholder_value}

    if tipo == "submit":
        # Un submit lo convierto en click al boton de submit
        return {"type": "click", "target": target}

    # Checkbox / radio: lo convierto en click
    if tipo == "change":
        return {"type": "click", "target": target}

    return None


def construir_workflow(steps_dsl, form_url):
    """
    Construyo el objeto workflow completo con la estructura DSL
    que pide el enunciado.
    """
    return {
        "id": "alta_producto_v2",
        "titulo": "Alta de Producto",
        "descripcion": (
            "Procedimiento para dar de alta un nuevo producto en el "
            "formulario web. Rellena nombre, precio, stock y categoria, "
            "y pulsa Guardar."
        ),
        "app": "formulario_productos",
        "url": form_url,
        "tags": ["alta", "producto", "formulario", "inventario"],
        "param_schema": {
            "nombre": {
                "type": "string",
                "description": "Nombre del producto",
                "required": True,
            },
            "precio": {
                "type": "float",
                "description": "Precio en euros",
                "required": True,
            },
            "stock": {
                "type": "integer",
                "description": "Unidades en stock",
                "required": True,
            },
            "categoria": {
                "type": "enum",
                "values": ["camisetas", "sudaderas", "pantalones", "accesorios"],
                "description": "Categoria del producto",
                "required": True,
            },
        },
        "steps": [
            {"type": "wait", "ms": 500},
            *steps_dsl,
            {
                "type": "wait_for_text",
                "target": {"by": "id", "value": "toast"},
                "contains": "Guardado",
            },
        ],
    }


def imprimir_resumen(actions):
    """Muestro un resumen de lo que se ha grabado."""
    print("\n" + "=" * 72)
    print("RESUMEN DE ACCIONES GRABADAS")
    print("=" * 72)
    for i, action in enumerate(actions, 1):
        tipo = action.get("type", "")
        selector = action.get("selector", "")
        value = action.get("value", "")
        extra = f" | valor={value!r}" if value else ""
        print(f"{i:02d}. {tipo:<7} {selector}{extra}")
    print("=" * 72)


def esperar_enter(stop_event):
    """Espero a que el usuario pulse ENTER para parar."""
    input(
        "\nInteractua con el formulario en el navegador.\n"
        "Cuando termines, pulsa ENTER aqui para detener la grabacion...\n"
    )
    stop_event.set()


def main():
    # Creo el directorio de salida si no existe
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    driver = crear_driver()
    stop_event = threading.Event()
    seen = 0

    try:
        print("Abriendo navegador...")
        driver.get(FORM_URL)
        print(f"Pagina cargada: {driver.title}")

        print("Instalando recorder JavaScript via execute_script()...")
        inyectar_recorder(driver)
        print("Recorder activo. El HTML no se ha modificado.")
        print("Ya puedes rellenar el formulario, hacer clic, seleccionar opciones, etc.")

        # Lanzo un hilo para esperar el ENTER del usuario
        t = threading.Thread(target=esperar_enter, args=(stop_event,), daemon=True)
        t.start()

        # Polling: voy recogiendo las acciones que captura el JS
        while not stop_event.is_set():
            actions = obtener_acciones(driver)
            if len(actions) > seen:
                nuevas = actions[seen:]
                for action in nuevas:
                    msg = f"[REC] {action['type']:<7} {action.get('selector', '')}"
                    if "value" in action:
                        msg += f" -> {action['value']!r}"
                    print(msg)
                seen = len(actions)
            time.sleep(POLL_INTERVAL)

        # Recojo todas las acciones finales
        actions = obtener_acciones(driver)
        print(f"\nGrabacion detenida. Total acciones: {len(actions)}")

        imprimir_resumen(actions)

        # Convierto las acciones crudas al formato DSL
        steps_dsl = []
        for action in actions:
            step = convertir_a_step_dsl(action)
            if step:
                steps_dsl.append(step)

        # Construyo el workflow completo
        workflow = construir_workflow(steps_dsl, FORM_URL)

        # Guardo el JSON
        workflow_id = workflow.get("id", "workflow_generico")
        output_file = OUTPUT_DIR / f"{workflow_id}.workflow.json"
        output_file.write_text(
            json.dumps(workflow, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"\n-> Workflow guardado en: {output_file}")
        print(f"   {len(steps_dsl)} pasos DSL generados")
        print(f"   Placeholders aplicados: {list(FIELD_PLACEHOLDERS.keys())}")

    finally:
        input("\nPulsa ENTER para cerrar el navegador...")
        driver.quit()


if __name__ == "__main__":
    main()
