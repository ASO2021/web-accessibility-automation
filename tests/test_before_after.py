"""Compara una pagina inaccesible con su version corregida (W3C BAD demo)."""
import pytest

from config import settings


@pytest.mark.demo
@pytest.mark.parametrize("page", list(settings.BAD_PAGES), ids=list(settings.BAD_PAGES))
def test_fixed_page_has_fewer_violations_than_inaccessible_page(driver, scan, page):
    before_url, after_url = settings.BAD_PAGES[page]

    # Setup + accion: escanear la version inaccesible
    driver.get(before_url)
    _, before = scan(f"bad_{page}_before", f"W3C BAD - {page} (before)")

    # Accion: escanear la version corregida
    driver.get(after_url)
    _, after = scan(f"bad_{page}_after", f"W3C BAD - {page} (after)")

    # Validacion
    assert before["rules_violated"] > 0, "La pagina inaccesible deberia tener violaciones"
    assert after["elements_affected"] < before["elements_affected"]
    assert after["by_impact"]["critical"] <= before["by_impact"]["critical"]
