import os

BROWSER = os.getenv("BROWSER", "chrome").lower()      # chrome | firefox | edge
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
WINDOW_SIZE = os.getenv("WINDOW_SIZE", "1366x768")
SCRIPT_TIMEOUT = int(os.getenv("SCRIPT_TIMEOUT", "60"))
TIMEOUT = int(os.getenv("TIMEOUT", "15"))
SLOW_MO = float(os.getenv("SLOW_MO", "2"))

# Reglas de axe-core que se ejecutan: solo criterios WCAG (A y AA)
WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]

REPORTS_DIR = os.getenv("REPORTS_DIR", "reports/accessibility")

# Paginas de ejemplo: W3C "Before and After Demonstration" (BAD)
# Cada par tiene una version inaccesible (before) y una corregida (after).
BAD_BASE = "https://www.w3.org/WAI/demos/bad"
BAD_PAGES = {
    "home": (f"{BAD_BASE}/before/home.html", f"{BAD_BASE}/after/home.html"),
    "survey": (f"{BAD_BASE}/before/survey.html", f"{BAD_BASE}/after/survey.html"),
}

SAUCEDEMO_URL = "https://www.saucedemo.com/"
SAUCEDEMO_USER = os.getenv("SAUCE_USER", "standard_user")
SAUCEDEMO_PASSWORD = os.getenv("SAUCE_PASSWORD", "secret_sauce")
