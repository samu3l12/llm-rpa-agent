"""
Ejecutor RPA con Selenium.
Recibe un workflow ya renderizado (sin placeholders) y ejecuta
cada step sobre el formulario web. Uso el mismo patron del profesor
en 06_rpa_completo_con_chain.py: WebDriverWait para esperas, retry
para robustez, y logging para trazabilidad.

Si un selector no encuentra el elemento, lanzo error inmediatamente.
Prefiero que falle a que haga algo inesperado en el formulario.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger("RPARunner")


class RPARunner:
    """
    Ejecuto workflows RPA paso a paso con Selenium.
    Cada tipo de step tiene su metodo dedicado.
    """

    def __init__(self, headless: bool = False, timeout: int = 10, debug_mode: bool = False):
        # _ Fuerza modo visual ignorando el .env si el flag desde MAUI lo pide
        self.headless = False if debug_mode else headless
        self.timeout = timeout
        self.debug_mode = debug_mode
        self.driver = None
        self.wait = None

    def _crear_driver(self):
        """Configuro y creo el navegador Chrome."""
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, self.timeout)
        logger.info("Navegador abierto (headless=%s)", self.headless)

    def _cerrar_driver(self):
        """Cierro el navegador si esta abierto."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("Navegador cerrado")

    def _resolver_locator(self, target: dict):
        """
        Convierto el target del step en un par (By, valor) para Selenium.
        Si el elemento no existe, fallo inmediatamente.
        """
        by_type = target.get("by", "css")
        value = target.get("value", "")

        if by_type == "id":
            return (By.ID, value)
        elif by_type == "name":
            return (By.NAME, value)
        elif by_type == "css":
            return (By.CSS_SELECTOR, value)
        elif by_type == "xpath":
            return (By.XPATH, value)
        else:
            return (By.CSS_SELECTOR, value)

    def _buscar_elemento(self, target: dict):
        """
        Busco el elemento con espera explicita.
        Si no aparece en el timeout, fallo con mensaje claro.
        """
        locator = self._resolver_locator(target)
        try:
            elemento = self.wait.until(
                EC.presence_of_element_located(locator)
            )
            return elemento
        except TimeoutException:
            raise RuntimeError(
                f"No encontre el elemento: by={target.get('by')}, "
                f"value='{target.get('value')}' (timeout={self.timeout}s). "
                f"Puede que la pagina haya cambiado."
            )

    def _exec_wait(self, step: dict):
        """Espero N milisegundos."""
        ms = step.get("ms", 500)
        logger.info("  wait %d ms", ms)
        time.sleep(ms / 1000)

    def _exec_click(self, step: dict):
        """Hago click en un elemento."""
        target = step["target"]
        elemento = self._buscar_elemento(target)
        # Uso wait para asegurarme de que sea clickable
        locator = self._resolver_locator(target)
        elemento = self.wait.until(EC.element_to_be_clickable(locator))
        elemento.click()
        logger.info("  click -> %s", target)
        if self.debug_mode:
            time.sleep(1) # _ Ralentiza artificialmente para ver la demo visual

    def _exec_type(self, step: dict):
        """Escribo texto en un input."""
        target = step["target"]
        value = str(step.get("value", ""))
        elemento = self._buscar_elemento(target)
        elemento.clear()
        elemento.send_keys(value)
        logger.info("  type -> %s = '%s'", target, value)
        if self.debug_mode:
            time.sleep(1) # _ Ralentiza artificialmente para ver la demo visual

    def _exec_select(self, step: dict):
        """Selecciono una opcion en un <select>."""
        target = step["target"]
        value = str(step.get("value", ""))
        elemento = self._buscar_elemento(target)
        select = Select(elemento)
        select.select_by_value(value)
        logger.info("  select -> %s = '%s'", target, value)
        if self.debug_mode:
            time.sleep(1) # _ Ralentiza artificialmente para ver la demo visual

    def _exec_wait_for_text(self, step: dict):
        """Espero a que un elemento contenga cierto texto."""
        target = step["target"]
        contains = step.get("contains", "")
        locator = self._resolver_locator(target)

        try:
            self.wait.until(
                EC.text_to_be_present_in_element(locator, contains)
            )
            logger.info("  wait_for_text -> '%s' encontrado en %s", contains, target)
        except TimeoutException:
            # Intento leer lo que hay para dar un error informativo
            try:
                elem = self.driver.find_element(*locator)
                actual = elem.text
            except Exception:
                actual = "(no accesible)"
            raise RuntimeError(
                f"Timeout esperando texto '{contains}' en {target}. "
                f"Texto actual: '{actual}'"
            )

    def run(self, workflow: dict) -> dict:
        """
        Ejecuto un workflow completo.
        Devuelvo un diccionario con el resultado para que la tool
        pueda informar al agente.
        """
        start_time = time.time()
        url = workflow.get("url", "")
        steps = workflow.get("steps", [])

        logger.info("=" * 50)
        logger.info("Ejecutando workflow: %s", workflow.get("id", "?"))
        logger.info("URL: %s", url)
        logger.info("Steps: %d", len(steps))
        logger.info("=" * 50)

        try:
            self._crear_driver()
            self.driver.get(url)
            logger.info("Pagina cargada: %s", self.driver.title)

            for i, step in enumerate(steps, 1):
                tipo = step.get("type", "")
                logger.info("[%d/%d] %s", i, len(steps), tipo)

                if tipo == "wait":
                    self._exec_wait(step)
                elif tipo == "click":
                    self._exec_click(step)
                elif tipo == "type":
                    self._exec_type(step)
                elif tipo == "select":
                    self._exec_select(step)
                elif tipo == "wait_for_text":
                    self._exec_wait_for_text(step)
                else:
                    logger.warning("  Tipo de step desconocido: %s", tipo)

            duration_ms = int((time.time() - start_time) * 1000)

            # Intento leer el toast para confirmar
            last_text = ""
            try:
                toast = self.driver.find_element(By.ID, "toast")
                last_text = toast.text
            except Exception:
                pass

            logger.info("Workflow completado en %d ms", duration_ms)

            return {
                "status": "ok",
                "duration_ms": duration_ms,
                "last_text": last_text,
                "workflow_id": workflow.get("id", ""),
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("Error ejecutando workflow: %s", e)

            # Capturo screenshot si es posible
            if self.driver:
                try:
                    self.driver.save_screenshot("error_rpa.png")
                    logger.error("Screenshot guardado: error_rpa.png")
                except Exception:
                    pass

            return {
                "status": "error",
                "duration_ms": duration_ms,
                "error_detail": str(e),
                "workflow_id": workflow.get("id", ""),
            }

        finally:
            self._cerrar_driver()
