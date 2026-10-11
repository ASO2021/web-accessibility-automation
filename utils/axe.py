"""Ejecuta axe-core dentro de la pagina abierta por Selenium.

axe-core (Deque Systems, licencia MPL-2.0) esta incluido en vendor/axe.min.js,
asi no hace falta internet para cargarlo y la version queda fija.
"""
import time
from pathlib import Path

from config import settings

AXE_PATH = Path(__file__).resolve().parent.parent / "vendor" / "axe.min.js"

_RUN_SCRIPT = """
const done = arguments[arguments.length - 1];
const runOnly = arguments[0];
axe.run(document, { runOnly })
  .then(results => done(results))
  .catch(error => done({ error: String(error) }));
"""

_CLEAR_REPORT_SCRIPT = """
const host = document.getElementById('axe-visual-report');
if (host) host.remove();
const style = document.getElementById('axe-visual-highlights');
if (style) style.remove();
document.querySelectorAll('[data-axe-visual-highlight]')
  .forEach(element => element.removeAttribute('data-axe-visual-highlight'));
"""

_SHOW_REPORT_SCRIPT = """
const results = arguments[0];
const violations = results.violations || [];
const host = document.createElement('div');
host.id = 'axe-visual-report';
host.style.cssText = 'all: initial; position: fixed; inset: auto 16px 16px auto; z-index: 2147483647;';
const shadow = host.attachShadow({ mode: 'open' });
shadow.innerHTML = `
  <style>
    * { box-sizing: border-box; }
    .panel {
      width: min(460px, calc(100vw - 32px));
      max-height: min(78vh, 760px);
      overflow: hidden;
      border: 2px solid #8c1515;
      border-radius: 10px;
      background: #fff;
      color: #1b1b1b;
      box-shadow: 0 8px 32px #0008;
      font: 14px/1.45 Arial, sans-serif;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      background: #8c1515;
      color: #fff;
    }
    h2 { margin: 0; font-size: 17px; }
    button {
      padding: 5px 9px;
      border: 1px solid currentColor;
      border-radius: 4px;
      background: transparent;
      color: inherit;
      cursor: pointer;
      font: inherit;
    }
    .content { max-height: calc(min(78vh, 760px) - 52px); overflow: auto; padding: 12px; }
    .count { margin: 0 0 10px; font-weight: 700; }
    .clean { padding: 12px; border: 1px solid #24723b; border-radius: 6px; color: #185b2d; }
    article { margin: 0 0 12px; padding: 10px; border: 1px solid #b7b7b7; border-radius: 6px; }
    article:last-child { margin-bottom: 0; }
    .impact { color: #8c1515; font-weight: 700; text-transform: uppercase; }
    h3 { margin: 4px 0; font-size: 15px; overflow-wrap: anywhere; }
    p { margin: 5px 0; }
    ul { margin: 6px 0 0; padding-left: 20px; }
    li { margin: 0 0 8px; overflow-wrap: anywhere; }
    code, pre { white-space: pre-wrap; overflow-wrap: anywhere; }
    pre { margin: 5px 0 0; padding: 7px; background: #f2f2f2; border-radius: 4px; }
    .refs { color: #404040; font-size: 12px; }
  </style>
  <section class="panel" role="region" aria-labelledby="axe-visual-title">
    <header>
      <h2 id="axe-visual-title">Resultados de accesibilidad</h2>
      <button type="button" aria-label="Cerrar resultados">Cerrar</button>
    </header>
    <div class="content"></div>
  </section>`;

const content = shadow.querySelector('.content');
const affected = violations.reduce((total, violation) =>
  total + (violation.nodes || []).length, 0);
const count = document.createElement('p');
count.className = 'count';
count.textContent = violations.length
  ? `${violations.length} regla(s) incumplida(s) · ${affected} elemento(s) afectado(s)`
  : 'No se encontraron errores en las reglas evaluadas.';
content.appendChild(count);

if (!violations.length) {
  const clean = document.createElement('p');
  clean.className = 'clean';
  clean.textContent = 'Esta pantalla no presenta violaciones detectadas por este escaneo.';
  content.appendChild(clean);
}

for (const violation of violations) {
  const card = document.createElement('article');
  const impact = document.createElement('div');
  impact.className = 'impact';
  impact.textContent = violation.impact || 'Impacto no especificado';
  const heading = document.createElement('h3');
  heading.textContent = violation.id || 'Regla desconocida';
  const help = document.createElement('p');
  help.textContent = violation.help || 'Sin descripción disponible.';
  const refs = document.createElement('p');
  refs.className = 'refs';
  refs.textContent = `WCAG: ${(violation.tags || []).filter(tag => tag.startsWith('wcag')).join(', ') || 'sin referencia'}`;
  const nodes = document.createElement('ul');

  for (const node of violation.nodes || []) {
    const item = document.createElement('li');
    const selectors = node.target || [];
    const selector = document.createElement('code');
    selector.textContent = selectors.join(' > ') || 'Selector no disponible';
    item.appendChild(selector);
    if (node.failureSummary) {
      const detail = document.createElement('pre');
      detail.textContent = node.failureSummary;
      item.appendChild(detail);
    }
    nodes.appendChild(item);

    for (const target of selectors) {
      try {
        document.querySelectorAll(target).forEach(element =>
          element.setAttribute('data-axe-visual-highlight', 'true'));
      } catch (error) {
        console.warn(`No se pudo resaltar el selector de axe: ${target}`, error);
      }
    }
  }
  card.append(impact, heading, help, refs, nodes);
  content.appendChild(card);
}

const highlightStyle = document.createElement('style');
highlightStyle.id = 'axe-visual-highlights';
highlightStyle.textContent =
  '[data-axe-visual-highlight] { outline: 3px solid #d00000 !important; outline-offset: 2px !important; }';
document.head.appendChild(highlightStyle);
shadow.querySelector('button').addEventListener('click', () => {
  host.remove();
  highlightStyle.remove();
  document.querySelectorAll('[data-axe-visual-highlight]')
    .forEach(element => element.removeAttribute('data-axe-visual-highlight'));
});
document.documentElement.appendChild(host);
"""


def inject_axe(driver):
    """Carga axe-core en la pagina actual."""
    driver.execute_script(AXE_PATH.read_text(encoding="utf-8"))


def run_axe(driver, tags=None, rules=None):
    """Escanea la pagina actual y devuelve el resultado crudo de axe."""
    if tags is not None and rules is not None:
        raise ValueError("Indica tags o rules, pero no ambos.")
    driver.set_script_timeout(settings.SCRIPT_TIMEOUT)
    driver.execute_script(_CLEAR_REPORT_SCRIPT)
    inject_axe(driver)
    run_only = (
        {"type": "rule", "values": rules}
        if rules is not None
        else {"type": "tag", "values": tags or settings.WCAG_TAGS}
    )
    results = driver.execute_async_script(_RUN_SCRIPT, run_only)
    if "error" in results:
        raise RuntimeError(f"axe fallo: {results['error']}")
    driver.execute_script(_SHOW_REPORT_SCRIPT, results)
    if not settings.HEADLESS and settings.SLOW_MO:
        time.sleep(settings.SLOW_MO)
    return results
