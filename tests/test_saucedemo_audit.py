"""Auditoria de SauceDemo: genera el reporte y comprueba que axe corrio.

No falla por las violaciones encontradas: el objetivo es obtener el informe.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import settings


@pytest.mark.audit
def test_audit_login_page(driver, scan):
    driver.get(settings.SAUCEDEMO_URL)

    results, summary = scan("saucedemo_login", "SauceDemo - Login page")

    assert "violations" in results
    assert summary["rules_passed"] > 0  # axe realmente evaluo reglas


@pytest.mark.audit
def test_audit_products_page(driver, scan):
    driver.get(settings.SAUCEDEMO_URL)
    driver.find_element(By.CSS_SELECTOR, "[data-test='username']").send_keys(settings.SAUCEDEMO_USER)
    driver.find_element(By.CSS_SELECTOR, "[data-test='password']").send_keys(settings.SAUCEDEMO_PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "[data-test='login-button']").click()
    WebDriverWait(driver, settings.TIMEOUT).until(EC.url_contains("inventory.html"))

    results, summary = scan("saucedemo_products", "SauceDemo - Products page")

    assert "violations" in results
    assert summary["rules_passed"] > 0
