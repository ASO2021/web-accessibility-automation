"""Navegacion solo con teclado (WCAG 2.1.1 Keyboard, 2.4.3 Focus Order)."""
import pytest
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from config import settings


def _focused(driver):
    """data-test del elemento que tiene el foco."""
    return driver.execute_script("return document.activeElement.getAttribute('data-test');")


@pytest.mark.keyboard
def test_login_form_tab_order(driver):
    driver.get(settings.SAUCEDEMO_URL)
    order = []

    for _ in range(3):
        ActionChains(driver).send_keys(Keys.TAB).pause(settings.SLOW_MO).perform()
        order.append(_focused(driver))

    assert order == ["username", "password", "login-button"]


@pytest.mark.keyboard
def test_login_using_only_the_keyboard(driver):
    driver.get(settings.SAUCEDEMO_URL)
    keys = ActionChains(driver)
    pause = settings.SLOW_MO

    keys.send_keys(Keys.TAB).pause(pause).send_keys(settings.SAUCEDEMO_USER).pause(pause)
    keys.send_keys(Keys.TAB).pause(pause).send_keys(settings.SAUCEDEMO_PASSWORD).pause(pause)
    keys.send_keys(Keys.TAB).pause(pause).send_keys(Keys.ENTER).pause(pause)
    keys.perform()

    WebDriverWait(driver, settings.TIMEOUT).until(EC.url_contains("inventory.html"))
    assert "inventory.html" in driver.current_url
