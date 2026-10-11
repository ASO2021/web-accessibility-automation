"""Twenty functional and accessibility smoke checks for SauceDemo."""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from config import settings
from utils.axe import run_axe
from utils.report import save_reports

AXE_RULES = ("html-has-lang", "label", "image-alt", "color-contrast")


def _open_login(driver):
    driver.get(settings.SAUCEDEMO_URL)
    driver.delete_all_cookies()
    driver.execute_script(
        "window.localStorage.clear(); window.sessionStorage.clear();"
    )
    driver.refresh()


def _login(driver, username=None, password=None):
    _open_login(driver)
    driver.find_element(By.ID, "user-name").send_keys(
        username if username is not None else settings.SAUCEDEMO_USER
    )
    driver.find_element(By.ID, "password").send_keys(
        password if password is not None else settings.SAUCEDEMO_PASSWORD
    )
    driver.find_element(By.ID, "login-button").click()


def _wait_for_inventory(driver):
    WebDriverWait(driver, settings.TIMEOUT).until(
        EC.url_contains("inventory.html")
    )
    WebDriverWait(driver, settings.TIMEOUT).until(
        EC.visibility_of_element_located((By.CLASS_NAME, "inventory_list"))
    )


def _add_backpack(driver):
    add_button = WebDriverWait(driver, settings.TIMEOUT).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "[data-test='add-to-cart-sauce-labs-backpack']")
        )
    )
    add_button.click()


def _start_checkout(driver):
    driver.find_element(By.CSS_SELECTOR, "[data-test='checkout']").click()
    WebDriverWait(driver, settings.TIMEOUT).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-test='firstName']"))
    )


@pytest.fixture(scope="module")
def accessibility_results(module_driver):
    """Runs selected axe checks once per page and saves evidence reports."""
    results = {}
    _open_login(module_driver)
    results["login"] = run_axe(module_driver, rules=AXE_RULES)
    save_reports(results["login"], "saucedemo_login_smoke", "SauceDemo login")

    _login(module_driver)
    _wait_for_inventory(module_driver)
    results["inventory"] = run_axe(module_driver, rules=AXE_RULES)
    save_reports(
        results["inventory"],
        "saucedemo_inventory_smoke",
        "SauceDemo inventory",
    )
    return results


@pytest.mark.smoke
@pytest.mark.functional
def test_login_page_shows_required_controls(module_driver):
    _open_login(module_driver)
    assert module_driver.find_element(By.ID, "user-name").is_displayed()
    assert module_driver.find_element(By.ID, "password").is_displayed()
    assert module_driver.find_element(By.ID, "login-button").is_displayed()


@pytest.mark.smoke
@pytest.mark.functional
def test_password_field_masks_input(module_driver):
    _open_login(module_driver)
    assert module_driver.find_element(By.ID, "password").get_attribute("type") == "password"


@pytest.mark.smoke
@pytest.mark.functional
def test_empty_login_reports_missing_username(module_driver):
    _open_login(module_driver)
    module_driver.find_element(By.ID, "login-button").click()
    error = module_driver.find_element(By.CSS_SELECTOR, "[data-test='error']")
    assert "Username is required" in error.text


@pytest.mark.smoke
@pytest.mark.functional
def test_invalid_login_is_rejected(module_driver):
    _login(module_driver, "invalid_user", "invalid_password")
    error = module_driver.find_element(By.CSS_SELECTOR, "[data-test='error']")
    assert "Username and password do not match" in error.text


@pytest.mark.smoke
@pytest.mark.functional
def test_locked_out_user_sees_access_error(module_driver):
    _login(module_driver, "locked_out_user", settings.SAUCEDEMO_PASSWORD)
    error = module_driver.find_element(By.CSS_SELECTOR, "[data-test='error']")
    assert "locked out" in error.text.lower()


@pytest.mark.smoke
@pytest.mark.functional
def test_standard_user_can_sign_in(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    assert module_driver.find_element(By.CLASS_NAME, "inventory_list").is_displayed()


@pytest.mark.smoke
@pytest.mark.functional
def test_inventory_contains_six_products(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    assert len(module_driver.find_elements(By.CLASS_NAME, "inventory_item")) == 6


@pytest.mark.smoke
@pytest.mark.functional
def test_products_sort_by_name_ascending(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    Select(module_driver.find_element(By.CLASS_NAME, "product_sort_container")).select_by_value("az")
    names = [item.text for item in module_driver.find_elements(By.CLASS_NAME, "inventory_item_name")]
    assert names == sorted(names)


@pytest.mark.smoke
@pytest.mark.functional
def test_products_sort_by_name_descending(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    Select(module_driver.find_element(By.CLASS_NAME, "product_sort_container")).select_by_value("za")
    names = [item.text for item in module_driver.find_elements(By.CLASS_NAME, "inventory_item_name")]
    assert names == sorted(names, reverse=True)


@pytest.mark.smoke
@pytest.mark.functional
def test_products_sort_by_price_ascending(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    Select(module_driver.find_element(By.CLASS_NAME, "product_sort_container")).select_by_value("lohi")
    prices = [
        float(item.text.replace("$", ""))
        for item in module_driver.find_elements(By.CLASS_NAME, "inventory_item_price")
    ]
    assert prices == sorted(prices)


@pytest.mark.smoke
@pytest.mark.functional
def test_products_sort_by_price_descending(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    Select(module_driver.find_element(By.CLASS_NAME, "product_sort_container")).select_by_value("hilo")
    prices = [
        float(item.text.replace("$", ""))
        for item in module_driver.find_elements(By.CLASS_NAME, "inventory_item_price")
    ]
    assert prices == sorted(prices, reverse=True)


@pytest.mark.smoke
@pytest.mark.functional
def test_adding_product_updates_cart_badge(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    _add_backpack(module_driver)
    assert module_driver.find_element(By.CLASS_NAME, "shopping_cart_badge").text == "1"


@pytest.mark.smoke
@pytest.mark.functional
def test_cart_displays_added_product_and_removes_it(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    _add_backpack(module_driver)
    module_driver.find_element(By.CLASS_NAME, "shopping_cart_link").click()
    assert "Sauce Labs Backpack" in module_driver.find_element(
        By.CLASS_NAME, "cart_item"
    ).text
    module_driver.find_element(
        By.CSS_SELECTOR, "[data-test='remove-sauce-labs-backpack']"
    ).click()
    assert module_driver.find_elements(By.CLASS_NAME, "cart_item") == []


@pytest.mark.smoke
@pytest.mark.functional
def test_product_details_can_return_to_inventory(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    module_driver.find_element(
        By.CSS_SELECTOR, "[data-test='item-4-title-link']"
    ).click()
    details_name = WebDriverWait(module_driver, settings.TIMEOUT).until(
        EC.visibility_of_element_located((By.CLASS_NAME, "inventory_details_name"))
    )
    assert details_name.is_displayed()
    module_driver.find_element(
        By.CSS_SELECTOR, "[data-test='back-to-products']"
    ).click()
    assert "inventory.html" in module_driver.current_url


@pytest.mark.smoke
@pytest.mark.functional
def test_checkout_requires_first_name(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    _add_backpack(module_driver)
    module_driver.find_element(By.CLASS_NAME, "shopping_cart_link").click()
    _start_checkout(module_driver)
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='continue']").click()
    error = WebDriverWait(module_driver, settings.TIMEOUT).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-test='error']"))
    )
    assert "First Name is required" in error.text


@pytest.mark.smoke
@pytest.mark.functional
def test_checkout_completes_order(module_driver):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    _add_backpack(module_driver)
    module_driver.find_element(By.CLASS_NAME, "shopping_cart_link").click()
    _start_checkout(module_driver)
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='firstName']").send_keys("Test")
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='lastName']").send_keys("User")
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='postalCode']").send_keys("1000")
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='continue']").click()
    WebDriverWait(module_driver, settings.TIMEOUT).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-test='finish']"))
    )
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='finish']").click()
    assert "Thank you for your order!" in module_driver.find_element(
        By.CSS_SELECTOR, "[data-test='complete-header']"
    ).text


@pytest.mark.smoke
@pytest.mark.accessibility
def test_login_page_declares_document_language(accessibility_results):
    assert any(
        result["id"] == "html-has-lang"
        for result in accessibility_results["login"]["passes"]
    )


@pytest.mark.smoke
@pytest.mark.accessibility
def test_login_form_labels_pass_axe_check(accessibility_results):
    assert any(
        result["id"] == "label"
        for result in accessibility_results["login"]["passes"]
    )


@pytest.mark.smoke
@pytest.mark.accessibility
def test_inventory_images_have_alternatives(accessibility_results):
    assert any(
        result["id"] == "image-alt"
        for result in accessibility_results["inventory"]["passes"]
    )


@pytest.mark.smoke
@pytest.mark.accessibility
def test_inventory_text_contrast_passes_axe_check(accessibility_results):
    assert any(
        result["id"] == "color-contrast"
        for result in accessibility_results["inventory"]["passes"]
    )


@pytest.mark.functional
@pytest.mark.smoke
@pytest.mark.parametrize(
    ("product_id", "product_name"),
    [
        ("sauce-labs-backpack", "Sauce Labs Backpack"),
        ("sauce-labs-bike-light", "Sauce Labs Bike Light"),
        ("sauce-labs-bolt-t-shirt", "Sauce Labs Bolt T-Shirt"),
    ],
    ids=["backpack", "bike-light", "bolt-t-shirt"],
)
def test_repeatable_purchase_flow(module_driver, product_id, product_name):
    _login(module_driver)
    _wait_for_inventory(module_driver)
    module_driver.find_element(
        By.CSS_SELECTOR, f"[data-test='add-to-cart-{product_id}']"
    ).click()
    assert module_driver.find_element(
        By.CLASS_NAME, "shopping_cart_badge"
    ).text == "1"

    module_driver.find_element(By.CLASS_NAME, "shopping_cart_link").click()
    assert module_driver.find_element(
        By.CLASS_NAME, "cart_item"
    ).find_element(By.CLASS_NAME, "inventory_item_name").text == product_name
    _start_checkout(module_driver)
    module_driver.find_element(
        By.CSS_SELECTOR, "[data-test='firstName']"
    ).send_keys("Test")
    module_driver.find_element(
        By.CSS_SELECTOR, "[data-test='lastName']"
    ).send_keys("User")
    module_driver.find_element(
        By.CSS_SELECTOR, "[data-test='postalCode']"
    ).send_keys("1000")
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='continue']").click()

    WebDriverWait(module_driver, settings.TIMEOUT).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-test='finish']"))
    )
    assert module_driver.find_element(
        By.CLASS_NAME, "cart_item"
    ).find_element(By.CLASS_NAME, "inventory_item_name").text == product_name
    module_driver.find_element(By.CSS_SELECTOR, "[data-test='finish']").click()
    confirmation = WebDriverWait(module_driver, settings.TIMEOUT).until(
        EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "[data-test='complete-header']")
        )
    )
    assert "Thank you for your order!" in confirmation.text
