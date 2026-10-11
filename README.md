# Web Accessibility Automation

Automated accessibility checks for web pages, written in Python.
It uses Selenium to open a page and [axe-core](https://github.com/dequelabs/axe-core) to scan it against WCAG 2.0, 2.1 and 2.2 (levels A and AA).
Each scan creates an HTML and a JSON report.

Automated tools find only part of the accessibility issues. This project is a first filter. Manual testing with a keyboard and a screen reader is still needed.

## What it does

| Test file | What it checks |
|-----------|----------------|
| `test_before_after.py` | Scans an inaccessible page and its fixed version (W3C "Before and After Demonstration"). The fixed page must have fewer problems. |
| `test_saucedemo_audit.py` | Scans the login and products pages of SauceDemo and creates the reports. |
| `test_keyboard.py` | Tab order of the login form, and a full login using only the keyboard. |
| `test_sauce_smoke_suite.py` | 20 high-impact functional and accessibility smoke checks for SauceDemo. |
| `test_report_unit.py` | Unit tests for the report code. They need no browser. |

The 20-case smoke suite covers login validation, authentication, inventory
content and sorting, cart updates, product details, checkout, and four focused
axe-core accessibility checks. It is a high-impact regression sample, not a
complete functional or WCAG conformance assessment.

## Project structure

```
config/settings.py     Browser, WCAG tags, pages to scan
utils/axe.py           Loads axe-core in the page and runs it
utils/report.py        Summary, JSON and HTML report
vendor/axe.min.js      axe-core 4.14.0 (MPL-2.0 license), so no internet is needed to load it
tests/                 Test cases
scan.py                Command line tool to scan any URL
conftest.py            Browser fixture, scan fixture, screenshot on failure
reports/accessibility/ Generated reports
```

## Setup

```bash
git clone <your-repo-url>
cd web-accessibility-automation
python -m venv .venv
.venv\Scripts\activate             # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

You need Python 3.10 or higher and Google Chrome.

## Run the tests

```bash
pytest                    # everything
pytest -m unit            # only tests without browser (fast)
pytest -m demo            # before and after comparison
pytest -m keyboard        # keyboard tests
pytest -m smoke           # all 20 functional and accessibility smoke checks
pytest -m functional      # functional SauceDemo flows
pytest -m accessibility   # focused axe-core checks
pytest --headless         # no browser window
pytest --browser firefox  # another browser
pytest --slow-mo 3        # pausa de 3 segundos para ver las acciones y cada prueba
```

## Scan any page

```bash
python scan.py https://www.saucedemo.com/
python scan.py https://example.com --name my_page --headless
```

The command prints a short summary and saves the reports in `reports/accessibility/`.
In visible browser runs, axe also shows an on-page panel for each scanned page,
lists every violation and affected selector, and outlines affected elements in red.
The panel also reports when no violations were detected.
For detectable contrast failures, the HTML and JSON reports include suggested
foreground colors, and a `.suggestions.css` file contains selectors and proposed
CSS overrides. These are proposals only: inspect and test them before applying,
especially for gradients, images, transparent colors, or hover/focus states.
Every scan also exports an Excel workbook with a summary and one row per
affected element; the HTML report includes a link to download that workbook.

## Scan color contrast

```bash
python scan_contrast.py https://www.saucedemo.com/
python scan_contrast.py https://example.com --name my_page --headless
```

The dedicated contrast scan checks axe-core's `color-contrast` rule against the
page's rendered content, prints each detected issue and affected element, and
saves HTML and JSON reports in `reports/accessibility/`. The browser is visible
by default; pass `--headless` to hide it. The scan covers content present in the
page DOM when axe runs; content that appears only after interaction or scrolling
must first be loaded or opened.
When a contrast failure contains supported color data, the reports also include
a proposed foreground color and a `.suggestions.css` file. Suggested CSS is not
injected into or automatically applied to the target site.
The Excel workbook's `Paleta` sheet lists every text/background pair axe
evaluated as conforming, failing, or requiring manual review. This is a text
contrast audit, not an inventory of decorative colors that do not render text.

## How to read a report

Each problem has an impact level: critical, serious, moderate or minor.
The report shows the rule, a short description, the WCAG tags, how many elements are affected, and examples of selectors.
Every rule links to a page that explains how to fix it.

## Design decisions

- axe-core is saved in the repo. The scan does not depend on a CDN, and the version is fixed.
- The audit tests of SauceDemo do not fail because of violations. Their goal is to produce the report.
- The 20-case smoke suite combines functional checks with a small set of axe-core accessibility assertions; those accessibility checks do not establish WCAG conformance.
- The before and after test compares two real pages. It shows that the tool finds problems and sees the improvement.
- Only WCAG rules run. Extra "best practice" rules are left out to keep the results focused on the standard.

## Limits

- axe-core does not test everything. For example, it cannot judge if an alt text is useful.
- Scans only check what is on screen at that moment. Pages with menus or dialogs need extra steps to open them first.
- Results can change when a new version of axe-core is used.
