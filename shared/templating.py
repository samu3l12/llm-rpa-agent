"""
Utilidad para sustituir placeholders en workflows.
Los placeholders tienen la forma {{nombre}}, {{precio}}, etc.
Recibo el workflow y un dict de parametros y devuelvo el workflow
con los valores reales ya insertados.
"""

import copy
import re
import json

# Patron para detectar placeholders tipo {{variable}}
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def render_workflow(workflow: dict, params: dict) -> dict:
    """
    Sustituyo los placeholders {{clave}} en los steps del workflow
    por los valores reales que vienen en params.

    Si falta algun parametro obligatorio, lanzo ValueError directamente
    porque prefiero que pete a que haga algo inesperado con el formulario.
    """
    rendered = copy.deepcopy(workflow)

    # Verifico que tengo todos los parametros necesarios
    schema = rendered.get("param_schema", {})
    for param_name, param_info in schema.items():
        is_required = param_info.get("required", False)
        if is_required and param_name not in params:
            raise ValueError(
                f"Falta el parametro obligatorio '{param_name}' "
                f"({param_info.get('description', 'sin descripcion')})"
            )

    # Sustituyo placeholders en cada step
    for step in rendered.get("steps", []):
        if "value" in step and isinstance(step["value"], str):
            step["value"] = _replace_placeholders(step["value"], params)

        if "contains" in step and isinstance(step["contains"], str):
            step["contains"] = _replace_placeholders(step["contains"], params)

    # Sustituyo tambien la URL si tiene placeholder
    if "url" in rendered and isinstance(rendered["url"], str):
        rendered["url"] = _replace_placeholders(rendered["url"], params)

    return rendered


def _replace_placeholders(text: str, params: dict) -> str:
    """
    Reemplazo cada {{variable}} por su valor real.
    Si el valor es numerico lo convierto a string para que
    Selenium pueda escribirlo en el campo.
    """
    def replacer(match):
        key = match.group(1)
        if key in params:
            return str(params[key])
        # Si no esta en params, dejo el placeholder tal cual
        # para que sea visible que algo falta
        return match.group(0)

    return _PLACEHOLDER_RE.sub(replacer, text)
