"""Escanea cualquier URL con axe-core y genera un reporte.

Uso:
    python scan.py https://www.saucedemo.com/
    python scan.py https://example.com --name mi_pagina --headless
"""
import argparse

from config import settings
from conftest import _build_driver
from utils.axe import run_axe
from utils.report import format_scan_results, safe_name, save_reports


def main():
    parser = argparse.ArgumentParser(description="Escaneo de accesibilidad con axe-core")
    parser.add_argument("url")
    parser.add_argument("--name", default=None, help="nombre del reporte")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    if args.headless:
        settings.HEADLESS = True
    driver = _build_driver()
    try:
        driver.get(args.url)
        results = run_axe(driver)
    finally:
        driver.quit()

    name = args.name or safe_name(args.url.split("//")[-1])
    json_path, html_path = save_reports(results, name, title=args.url)
    print(format_scan_results(results))
    print(f"Reporte HTML: {html_path}")
    print(f"Reporte JSON: {json_path}")
    print(f"Propuestas CSS (no aplicadas): {json_path.with_suffix('.suggestions.css')}")
    print(f"Export Excel: {json_path.with_suffix('.xlsx')}")


if __name__ == "__main__":
    main()
