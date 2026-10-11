import os
import time
from datetime import datetime

import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.event_firing_webdriver import (
    AbstractEventListener,
    EventFiringWebDriver,
)

from config import settings
from utils.axe import run_axe
from utils.report import format_scan_results, save_reports, summarize


def pytest_addoption(parser):
    group = parser.getgroup("accessibility")
    group.addoption("--browser", default=None, help="chrome | firefox | edge")
    group.addoption("--headless", action="store_true", default=False,
                    help="correr sin abrir la ventana del navegador")
    group.addoption(
        "--slow-mo",
        type=float,
        default=2.0,
        help="pausa en segundos tras navegar, hacer clic, escribir y cerrar cada prueba",
    )


def pytest_configure(config):
    if config.getoption("--browser"):
        settings.BROWSER = config.getoption("--browser").lower()
    if config.getoption("--headless"):
        settings.HEADLESS = True
    settings.SLOW_MO = config.getoption("--slow-mo")
    if settings.SLOW_MO < 0:
        raise pytest.UsageError("--slow-mo debe ser cero o mayor.")


class _VisualDelayListener(AbstractEventListener):
    """Deja tiempo para observar las acciones del navegador durante las pruebas."""

    @staticmethod
    def _pause():
        if not settings.HEADLESS and settings.SLOW_MO:
            time.sleep(settings.SLOW_MO)

    def after_navigate_to(self, url, driver):
        self._pause()

    def after_click(self, element, driver):
        self._pause()

    def after_change_value_of(self, element, driver):
        self._pause()


def _build_driver():
    width, height = settings.WINDOW_SIZE.split("x")
    browser = settings.BROWSER
    if browser == "firefox":
        options = FirefoxOptions()
        if settings.HEADLESS:
            options.add_argument("-headless")
        driver = webdriver.Firefox(options=options)
    elif browser == "edge":
        options = EdgeOptions()
        if settings.HEADLESS:
            options.add_argument("--headless=new")
        driver = webdriver.Edge(options=options)
    else:
        options = ChromeOptions()
        if settings.HEADLESS:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_experimental_option("prefs", {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.password_manager_leak_detection": False,
        })
        driver = webdriver.Chrome(options=options)
    driver.set_window_size(int(width), int(height))
    return driver


@pytest.fixture
def driver():
    raw_driver = _build_driver()
    driver = EventFiringWebDriver(raw_driver, _VisualDelayListener())
    try:
        yield driver
    finally:
        _VisualDelayListener._pause()
        driver.quit()


@pytest.fixture
def scan(driver):
    """Escanea la pagina actual con axe, guarda el reporte y devuelve (resultado, resumen)."""
    def _scan(name, title=None):
        results = run_axe(driver)
        json_path, html_path = save_reports(results, name, title)
        print(format_scan_results(results), flush=True)
        print(f"Reporte HTML: {html_path}", flush=True)
        print(f"Reporte JSON: {json_path}", flush=True)
        print(
            f"Propuestas CSS (no aplicadas): "
            f"{json_path.with_suffix('.suggestions.css')}",
            flush=True,
        )
        print(f"Export Excel: {json_path.with_suffix('.xlsx')}", flush=True)
        return results, summarize(results)
    return _scan


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Si un test falla, guarda un screenshot."""
    outcome = yield
    report = outcome.get_result()
    if report.when != "call" or report.passed:
        return
    driver = item.funcargs.get("driver")
    if driver is None:
        return
    os.makedirs("reports/screenshots", exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    driver.save_screenshot(f"reports/screenshots/{item.name}_{stamp}.png")
