"""Resumen y reportes (JSON y HTML) a partir del resultado de axe."""
import html
import json
import re
from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.table import Table, TableStyleInfo

from config import settings

IMPACT_ORDER = ["critical", "serious", "moderate", "minor"]


def summarize(results):
    """Cuenta violaciones por nivel de impacto."""
    violations = results.get("violations", [])
    by_impact = Counter(v.get("impact") or "minor" for v in violations)
    return {
        "url": results.get("url", ""),
        "rules_violated": len(violations),
        "elements_affected": sum(len(v.get("nodes", [])) for v in violations),
        "rules_passed": len(results.get("passes", [])),
        "by_impact": {level: by_impact.get(level, 0) for level in IMPACT_ORDER},
    }


def _hex_rgb(color):
    """Convierte colores HEX de axe a RGB; otros formatos no se estiman."""
    if not isinstance(color, str):
        return None
    match = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", color)
    if not match:
        return None
    value = match.group(1)
    if len(value) == 3:
        value = "".join(channel * 2 for channel in value)
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _relative_luminance(rgb):
    channels = []
    for channel in rgb:
        normalized = channel / 255
        channels.append(
            normalized / 12.92
            if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return sum(weight * channel for weight, channel in zip(
        (0.2126, 0.7152, 0.0722), channels
    ))


def _contrast_ratio(first, second):
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


def _nearest_contrast_color(foreground, background, minimum_ratio):
    """Busca el menor cambio RGB hacia blanco o negro que alcanza el umbral."""
    candidates = []
    for endpoint in ((0, 0, 0), (255, 255, 255)):
        if _contrast_ratio(endpoint, background) < minimum_ratio:
            continue

        low, high = 0.0, 1.0
        for _ in range(24):
            amount = (low + high) / 2
            color = tuple(
                round(start + (end - start) * amount)
                for start, end in zip(foreground, endpoint)
            )
            if _contrast_ratio(color, background) >= minimum_ratio:
                high = amount
            else:
                low = amount

        color = tuple(
            round(start + (end - start) * high)
            for start, end in zip(foreground, endpoint)
        )
        while _contrast_ratio(color, background) < minimum_ratio:
            color = tuple(
                min(max(channel + (1 if end > start else -1), 0), 255)
                for channel, start, end in zip(color, foreground, endpoint)
            )
        distance = sum((start - end) ** 2 for start, end in zip(foreground, color))
        candidates.append((distance, color))

    if not candidates:
        return None
    return min(candidates, key=lambda candidate: candidate[0])[1]


def contrast_recommendations(results):
    """Sugiere un color de texto conforme para fallos con colores HEX conocidos."""
    recommendations = []
    for violation in results.get("violations", []):
        if violation.get("id") != "color-contrast":
            continue
        for node in violation.get("nodes", []):
            targets = node.get("target", [])
            selector = ", ".join(str(target) for target in targets)
            for check in node.get("any", []):
                if check.get("id") != "color-contrast":
                    continue
                data = check.get("data") or {}
                foreground = _hex_rgb(data.get("fgColor"))
                background = _hex_rgb(data.get("bgColor"))
                ratio_text = str(data.get("expectedContrastRatio", "4.5:1"))
                ratio_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", ratio_text)
                minimum_ratio = float(ratio_match.group(1)) if ratio_match else 4.5
                if (not selector or any(char in selector for char in "{};\r\n")
                        or foreground is None or background is None):
                    recommendations.append({
                        "selector": selector or None,
                        "current_foreground": data.get("fgColor"),
                        "background": data.get("bgColor"),
                        "minimum_ratio": minimum_ratio,
                        "suggested_foreground": None,
                        "status": "manual_review",
                    })
                    continue

                suggested = _nearest_contrast_color(
                    foreground, background, minimum_ratio
                )
                recommendations.append({
                    "selector": selector,
                    "current_foreground": data.get("fgColor"),
                    "background": data.get("bgColor"),
                    "current_ratio": data.get("contrastRatio"),
                    "minimum_ratio": minimum_ratio,
                    "suggested_foreground": (
                        "#{:02x}{:02x}{:02x}".format(*suggested)
                        if suggested is not None else None
                    ),
                    "status": "css_available" if suggested is not None else "manual_review",
                })
    return recommendations


def contrast_color_audit(results):
    """Lista combinaciones de texto/fondo evaluadas por la regla color-contrast."""
    audit = []
    status_by_result = (
        ("passes", "conforme"),
        ("violations", "error"),
        ("incomplete", "revision_manual"),
    )
    seen = set()
    for result_key, status in status_by_result:
        for rule_result in results.get(result_key, []):
            if rule_result.get("id") != "color-contrast":
                continue
            for node in rule_result.get("nodes", []):
                checks = [
                    check
                    for key in ("any", "all", "none")
                    for check in node.get(key, [])
                    if check.get("id") == "color-contrast"
                ]
                if not checks:
                    checks = [{}]
                for check in checks:
                    data = check.get("data") or {}
                    targets = node.get("target", [])
                    selector = " > ".join(map(str, targets))
                    record_status = (
                        status
                        if data.get("fgColor") and data.get("bgColor")
                        and data.get("contrastRatio") is not None
                        else "revision_manual"
                    )
                    key = (
                        record_status,
                        selector,
                        data.get("fgColor"),
                        data.get("bgColor"),
                        data.get("contrastRatio"),
                    )
                    if key in seen:
                        continue
                    seen.add(key)
                    audit.append({
                        "status": record_status,
                        "selector": selector,
                        "foreground": data.get("fgColor"),
                        "background": data.get("bgColor"),
                        "contrast_ratio": data.get("contrastRatio"),
                        "minimum_ratio": data.get("expectedContrastRatio"),
                        "detail": (
                            check.get("message")
                            or node.get("failureSummary")
                            or "axe no proporcionó detalle adicional."
                        ),
                    })
    return audit


def build_contrast_css(results):
    """Genera propuestas CSS sin aplicarlas a la página escaneada."""
    lines = [
        "/* Propuestas generadas por axe; revisar antes de aplicar al sitio. */",
        "/* Solo se modifican colores de texto; verifica estados hover/focus y diseño. */",
        "",
    ]
    for recommendation in contrast_recommendations(results):
        selector = recommendation.get("selector")
        color = recommendation.get("suggested_foreground")
        if selector and color:
            lines.extend([
                f"{selector} {{",
                f"  color: {color} !important;",
                "}",
                "",
            ])
    if len(lines) == 3:
        lines.append("/* No hay correcciones CSS automáticas disponibles. */\n")
    return "\n".join(lines)


def format_scan_results(results):
    """Formatea el resumen y el detalle de violaciones para la consola."""
    summary = summarize(results)
    lines = [
        f"Reglas violadas: {summary['rules_violated']} | "
        f"Elementos afectados: {summary['elements_affected']}"
    ]
    lines.extend(f"  {level}: {count}" for level, count in summary["by_impact"].items())

    color_audit = contrast_color_audit(results)
    if color_audit:
        color_counts = Counter(row["status"] for row in color_audit)
        lines.append(
            "Pares de contraste: "
            f"{len(color_audit)} | conformes: {color_counts.get('conforme', 0)} | "
            f"errores: {color_counts.get('error', 0)} | "
            f"revisión manual: {color_counts.get('revision_manual', 0)}"
        )

    violations = results.get("violations", [])
    if not violations:
        lines.append("No se encontraron errores de accesibilidad en las reglas WCAG ejecutadas.")
        return "\n".join(lines)

    lines.append("\nErrores encontrados:")
    for violation in violations:
        impact = violation.get("impact") or "sin impacto"
        lines.append(f"\n[{impact.upper()}] {violation.get('id', 'regla desconocida')}")
        lines.append(f"  Problema: {violation.get('help', 'Sin descripcion disponible')}")
        tags = [tag for tag in violation.get("tags", []) if tag.startswith("wcag")]
        lines.append(f"  WCAG: {', '.join(tags) if tags else 'Sin referencia WCAG'}")
        for index, node in enumerate(violation.get("nodes", []), start=1):
            targets = node.get("target", [])
            lines.append(
                f"  Elemento {index}: "
                f"{' > '.join(map(str, targets)) or 'selector no disponible'}"
            )
            failure_summary = node.get("failureSummary")
            if failure_summary:
                indented_summary = failure_summary.replace("\n", "\n    ")
                lines.append(f"    Detalle: {indented_summary}")

    recommendations = contrast_recommendations(results)
    if recommendations:
        lines.append("\nPropuestas de correccion de contraste (no aplicadas):")
        for recommendation in recommendations:
            lines.append(
                f"  Selector: {recommendation.get('selector') or 'no disponible'}"
            )
            lines.append(
                "  Color de texto sugerido: "
                f"{recommendation.get('suggested_foreground') or 'requiere revision manual'} "
                f"(fondo {recommendation.get('background') or 'desconocido'}, "
                f"umbral {recommendation['minimum_ratio']}:1)"
            )

    return "\n".join(lines)


def serious_or_critical(results):
    """Reglas violadas con impacto serio o critico."""
    return [v for v in results.get("violations", []) if v.get("impact") in ("serious", "critical")]


def wcag_refs(violation):
    """Etiquetas WCAG de una regla, ej: ['wcag111', 'wcag2a']."""
    return sorted(t for t in violation.get("tags", []) if t.startswith("wcag"))


def safe_name(text):
    """Convierte un texto en un nombre de archivo seguro."""
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_").lower() or "report"


def _sorted_violations(results):
    def key(v):
        impact = v.get("impact") or "minor"
        return IMPACT_ORDER.index(impact) if impact in IMPACT_ORDER else len(IMPACT_ORDER)
    return sorted(results.get("violations", []), key=key)


def build_html(results, title, export_filename=None):
    summary = summarize(results)
    rows = []
    for v in _sorted_violations(results):
        impact = v.get("impact") or "minor"
        targets = []
        for node in v.get("nodes", [])[:3]:
            target = node.get("target", [])
            targets.append(html.escape(" > ".join(map(str, target))) if target else "")
        rows.append(
            "<tr>"
            f"<td><span class='tag {html.escape(impact)}'>{html.escape(impact)}</span></td>"
            f"<td><a href='{html.escape(v.get('helpUrl', '#'))}'>{html.escape(v.get('id', ''))}</a></td>"
            f"<td>{html.escape(v.get('help', ''))}</td>"
            f"<td>{html.escape(', '.join(wcag_refs(v)))}</td>"
            f"<td>{len(v.get('nodes', []))}</td>"
            f"<td><code>{'<br>'.join(targets)}</code></td>"
            "</tr>"
        )
    body = "\n".join(rows) or "<tr><td colspan='6'>No violations found.</td></tr>"
    recommendations = contrast_recommendations(results)
    recommendation_rows = []
    for recommendation in recommendations:
        recommendation_rows.append(
            "<tr>"
            f"<td><code>{html.escape(recommendation.get('selector') or 'No disponible')}</code></td>"
            f"<td><code>{html.escape(str(recommendation.get('current_foreground') or 'Desconocido'))}</code></td>"
            f"<td><code>{html.escape(str(recommendation.get('background') or 'Desconocido'))}</code></td>"
            f"<td><code>{html.escape(str(recommendation.get('suggested_foreground') or 'Revisión manual'))}</code></td>"
            f"<td>{recommendation['minimum_ratio']}:1</td>"
            "</tr>"
        )
    recommendations_html = ""
    if recommendation_rows:
        recommendations_html = f"""
<h2>Sugerencias de corrección de contraste (no aplicadas)</h2>
<p>Las sugerencias cambian el color del texto y deben revisarse visualmente antes de aplicarse.</p>
<table>
<thead><tr><th>Selector CSS</th><th>Texto actual</th><th>Fondo</th><th>Texto sugerido</th><th>Ratio mínimo</th></tr></thead>
<tbody>{"".join(recommendation_rows)}</tbody>
</table>
"""
    color_audit_rows = []
    for row in contrast_color_audit(results):
        color_audit_rows.append(
            "<tr>"
            f"<td>{html.escape(row['status'])}</td>"
            f"<td><code>{html.escape(row.get('selector') or 'No disponible')}</code></td>"
            f"<td><code>{html.escape(str(row.get('foreground') or 'No detectado'))}</code></td>"
            f"<td><code>{html.escape(str(row.get('background') or 'No detectado'))}</code></td>"
            f"<td>{html.escape(str(row.get('contrast_ratio') or 'No calculado'))}</td>"
            f"<td>{html.escape(str(row.get('minimum_ratio') or 'No disponible'))}</td>"
            f"<td>{html.escape(str(row.get('detail') or ''))}</td>"
            "</tr>"
        )
    color_audit_html = ""
    if color_audit_rows:
        color_audit_html = f"""
<h2>Análisis de combinaciones de contraste</h2>
<p>Incluye las combinaciones de texto y fondo que axe pudo evaluar en el DOM cargado.</p>
<table>
<thead><tr><th>Estado</th><th>Elemento</th><th>Texto</th><th>Fondo</th><th>Ratio</th><th>Mínimo</th><th>Detalle</th></tr></thead>
<tbody>{"".join(color_audit_rows)}</tbody>
</table>
"""
    export_html = ""
    if export_filename:
        export_html = (
            f"<p><a href='{html.escape(export_filename, quote=True)}' "
            "download>Exportar hallazgos a Excel (.xlsx)</a></p>"
        )
    cards = "".join(
        f"<div class='card {level}'><b>{summary['by_impact'][level]}</b><span>{level}</span></div>"
        for level in IMPACT_ORDER
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} - Accessibility report</title>
<style>
  body {{ font-family: system-ui, Arial, sans-serif; margin: 2rem; color: #1a1a1a; background: #fff; }}
  h1 {{ font-size: 1.5rem; margin-bottom: .25rem; }}
  .meta {{ color: #444; margin-bottom: 1.5rem; word-break: break-all; }}
  .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .card {{ border: 1px solid #ccc; border-radius: 8px; padding: .75rem 1.25rem; min-width: 110px; }}
  .card b {{ display: block; font-size: 1.75rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: .5rem; text-align: left; vertical-align: top; }}
  th {{ background: #f3f3f3; }}
  .tag {{ padding: .1rem .5rem; border-radius: 4px; font-weight: 600; color: #fff; }}
  .critical {{ background: #8b0000; }} .serious {{ background: #b34700; }}
  .moderate {{ background: #5b5b00; }} .minor {{ background: #3b3b3b; }}
  a {{ color: #0b5cad; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<p class="meta">URL: {html.escape(summary['url'])}<br>
Rules violated: {summary['rules_violated']} | Elements affected: {summary['elements_affected']} | Rules passed: {summary['rules_passed']}</p>
{export_html}
<div class="cards">{cards}</div>
<table>
<thead><tr><th>Impact</th><th>Rule</th><th>Problem</th><th>WCAG tags</th><th>Elements</th><th>Examples</th></tr></thead>
<tbody>
{body}
</tbody>
</table>
{color_audit_html}
{recommendations_html}
<p class="meta">Scanned with axe-core {html.escape(str(results.get('testEngine', {}).get('version', '')))}. Automated checks find only part of the issues. Manual testing is still needed.</p>
</body>
</html>"""


def _excel_value(value):
    """Neutraliza texto externo que Excel podría interpretar como fórmula."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _add_excel_table(sheet, name, last_column, last_row):
    if last_row < 2:
        return
    table = Table(displayName=name, ref=f"A1:{last_column}{last_row}")
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    sheet.add_table(table)


def _write_excel_report(results, path, title):
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "Resumen"
    summary_sheet.sheet_properties.tabColor = "1F4E78"
    summary = summarize(results)
    recommendations = contrast_recommendations(results)
    color_audit = contrast_color_audit(results)
    violations = results.get("violations", [])

    summary_sheet.merge_cells("A1:F1")
    summary_sheet["A1"] = "INFORME DE ACCESIBILIDAD"
    summary_sheet["A1"].font = Font(name="Aptos Display", size=20, bold=True, color="FFFFFF")
    summary_sheet["A1"].fill = PatternFill("solid", fgColor="17365D")
    summary_sheet["A1"].alignment = Alignment(vertical="center")
    summary_sheet.row_dimensions[1].height = 38
    summary_sheet.merge_cells("A2:F2")
    summary_sheet["A2"] = _excel_value(title)
    summary_sheet["A2"].font = Font(size=14, bold=True, color="17365D")
    summary_sheet["A2"].alignment = Alignment(wrap_text=True, vertical="center")
    summary_sheet.row_dimensions[2].height = 30

    summary_sheet["A4"] = "URL evaluada"
    summary_sheet["A4"].font = Font(bold=True, color="FFFFFF")
    summary_sheet["A4"].fill = PatternFill("solid", fgColor="4472C4")
    summary_sheet.merge_cells("B4:F4")
    summary_sheet["B4"] = _excel_value(summary["url"])
    summary_sheet["B4"].hyperlink = summary["url"] or None
    if summary["url"]:
        summary_sheet["B4"].style = "Hyperlink"
    summary_sheet["B4"].alignment = Alignment(wrap_text=True, vertical="center")
    summary_sheet.row_dimensions[4].height = 30

    summary_sheet.merge_cells("A6:B6")
    summary_sheet["A6"] = "INDICADORES"
    summary_sheet.merge_cells("D6:F6")
    summary_sheet["D6"] = "HALLAZGOS POR IMPACTO"
    for cell_ref in ("A6", "D6"):
        cell = summary_sheet[cell_ref]
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="4472C4")
        cell.alignment = Alignment(vertical="center")

    metrics = [
        ("Reglas incumplidas", summary["rules_violated"]),
        ("Elementos afectados", summary["elements_affected"]),
        ("Reglas aprobadas", summary["rules_passed"]),
        ("Sugerencias de contraste", len(recommendations)),
        ("Combinaciones evaluadas", len(color_audit)),
    ]
    for row_number, (label, value) in enumerate(metrics, start=7):
        summary_sheet.cell(row_number, 1, label)
        summary_sheet.cell(row_number, 2, value)
        summary_sheet.cell(row_number, 1).font = Font(bold=True, color="404040")
        summary_sheet.cell(row_number, 2).font = Font(size=13, bold=True, color="17365D")
        summary_sheet.cell(row_number, 2).alignment = Alignment(horizontal="center")

    summary_sheet["D7"] = "Impacto"
    summary_sheet["E7"] = "Reglas"
    summary_sheet["F7"] = "Elementos"
    for cell in summary_sheet[7][3:6]:
        cell.font = Font(bold=True, color="404040")
        cell.fill = PatternFill("solid", fgColor="D9E2F3")

    impact_fills = {
        "critical": "F4CCCC",
        "serious": "FCE4D6",
        "moderate": "FFF2CC",
        "minor": "E2F0D9",
    }
    for row_number, impact in enumerate(IMPACT_ORDER, start=8):
        rules_count = summary["by_impact"][impact]
        elements_count = sum(
            len(violation.get("nodes", []))
            for violation in violations
            if (violation.get("impact") or "minor") == impact
        )
        summary_sheet.cell(row_number, 4, impact.capitalize())
        summary_sheet.cell(row_number, 5, rules_count)
        summary_sheet.cell(row_number, 6, elements_count)
        for cell in summary_sheet[row_number][3:6]:
            cell.fill = PatternFill("solid", fgColor=impact_fills[impact])

    summary_sheet.merge_cells("A13:F13")
    summary_sheet["A13"] = "Cómo interpretar este informe"
    summary_sheet["A13"].font = Font(bold=True, color="FFFFFF")
    summary_sheet["A13"].fill = PatternFill("solid", fgColor="4472C4")
    notes = [
        "Cada fila de «Hallazgos» representa un elemento afectado por una regla.",
        "Los ratios de contraste y colores aparecen cuando axe pudo calcularlos.",
        "Las propuestas de la hoja «Contraste» son sugerencias; no se aplican al sitio.",
        "La automatización detecta solo una parte de los problemas: completa con revisión manual.",
    ]
    for row_number, note in enumerate(notes, start=14):
        summary_sheet.merge_cells(start_row=row_number, start_column=1, end_row=row_number, end_column=6)
        cell = summary_sheet.cell(row_number, 1, note)
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        summary_sheet.row_dimensions[row_number].height = 25

    findings = workbook.create_sheet("Hallazgos")
    findings.sheet_properties.tabColor = "C0504D"
    headers = [
        "Impacto", "Regla", "Descripción", "Criterios WCAG", "Elemento afectado (selector)",
        "Texto actual", "Fondo", "Contraste actual", "Contraste mínimo",
        "Texto sugerido", "Estado de sugerencia", "Detalle del problema", "Referencia",
    ]
    findings.append(headers)
    recommendations_by_selector = {
        recommendation["selector"]: recommendation
        for recommendation in recommendations
        if recommendation.get("selector")
    }

    for violation in _sorted_violations(results):
        for node in violation.get("nodes", []):
            targets = node.get("target", [])
            selector = " > ".join(map(str, targets))
            recommendation = recommendations_by_selector.get(selector, {})
            contrast_check = next(
                (
                    check.get("data") or {}
                    for check in node.get("any", [])
                    if check.get("id") == "color-contrast"
                ),
                {},
            )
            findings.append([
                _excel_value((violation.get("impact") or "sin impacto").capitalize()),
                _excel_value(violation.get("id", "")),
                _excel_value(violation.get("help", "")),
                _excel_value(", ".join(wcag_refs(violation))),
                _excel_value(selector),
                _excel_value(contrast_check.get("fgColor", "")),
                _excel_value(contrast_check.get("bgColor", "")),
                contrast_check.get("contrastRatio", ""),
                recommendation.get("minimum_ratio", ""),
                _excel_value(recommendation.get("suggested_foreground", "")),
                _excel_value({
                    "css_available": "CSS sugerido",
                    "manual_review": "Revisión manual",
                }.get(recommendation.get("status"), "")),
                _excel_value(node.get("failureSummary", "")),
                _excel_value(violation.get("helpUrl", "")),
            ])
            if violation.get("helpUrl"):
                findings.cell(findings.max_row, 13).hyperlink = violation["helpUrl"]
                findings.cell(findings.max_row, 13).style = "Hyperlink"

    contrast_sheet = workbook.create_sheet("Contraste")
    contrast_sheet.sheet_properties.tabColor = "70AD47"
    contrast_sheet.append([
        "Elemento afectado (selector)", "Color de texto actual", "Color de fondo",
        "Ratio actual", "Ratio mínimo requerido", "Color sugerido",
        "CSS sugerido", "Estado", "Nota",
    ])
    for recommendation in recommendations:
        selector = recommendation.get("selector") or ""
        suggested = recommendation.get("suggested_foreground") or ""
        status = {
            "css_available": "Propuesta disponible",
            "manual_review": "Requiere revisión manual",
        }.get(recommendation.get("status"), "Sin propuesta")
        contrast_sheet.append([
            _excel_value(selector),
            _excel_value(recommendation.get("current_foreground") or ""),
            _excel_value(recommendation.get("background") or ""),
            recommendation.get("current_ratio", ""),
            recommendation.get("minimum_ratio", ""),
            _excel_value(suggested),
            _excel_value(
                f"{selector} {{ color: {suggested} !important; }}"
                if selector and suggested else ""
            ),
            status,
            "No aplicar sin revisar contexto visual, estados interactivos y diseño.",
        ])
    if not recommendations:
        contrast_sheet.append([
            "No se detectaron fallos de contraste con propuestas de color.",
            "", "", "", "", "", "", "", "",
        ])

    palette_sheet = workbook.create_sheet("Paleta")
    palette_sheet.sheet_properties.tabColor = "5B9BD5"
    palette_sheet.append([
        "Resultado", "Elemento afectado (selector)", "Color de texto",
        "Color de fondo", "Ratio medido", "Ratio mínimo", "Detalle",
    ])
    for audit_row in color_audit:
        palette_sheet.append([
            audit_row["status"].replace("_", " ").capitalize(),
            _excel_value(audit_row.get("selector") or ""),
            _excel_value(audit_row.get("foreground") or ""),
            _excel_value(audit_row.get("background") or ""),
            audit_row.get("contrast_ratio", ""),
            audit_row.get("minimum_ratio", ""),
            _excel_value(audit_row.get("detail") or ""),
        ])
    if not color_audit:
        palette_sheet.append([
            "axe no devolvió combinaciones de contraste evaluables para esta página.",
            "", "", "", "", "", "",
        ])

    _add_excel_table(findings, "AccessibilityFindings", "M", findings.max_row)
    if recommendations:
        _add_excel_table(contrast_sheet, "ContrastRecommendations", "I", contrast_sheet.max_row)
    if color_audit:
        _add_excel_table(palette_sheet, "ContrastColorAudit", "G", palette_sheet.max_row)

    thin_gray = Side(style="thin", color="D9E1F2")
    for sheet in (findings, contrast_sheet, palette_sheet):
        sheet.freeze_panes = "A2"
        sheet.sheet_view.showGridLines = False
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="17365D")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.row_dimensions[1].height = 34
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = Border(bottom=thin_gray)
            sheet.row_dimensions[row[0].row].height = 58
        if sheet.max_row > 1:
            sheet.auto_filter.ref = sheet.dimensions

    for row in findings.iter_rows(min_row=2):
        impact = str(row[0].value).lower()
        fill = impact_fills.get(impact)
        if fill:
            row[0].fill = PatternFill("solid", fgColor=fill)
            row[0].font = Font(bold=True, color="404040")
        for ratio_cell in (row[7], row[8]):
            if isinstance(ratio_cell.value, (int, float)):
                ratio_cell.number_format = '0.00" : 1"'
    for row in contrast_sheet.iter_rows(min_row=2):
        for column in (2, 3, 6):
            value = row[column - 1].value
            if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                cell = row[column - 1]
                cell.fill = PatternFill("solid", fgColor=value[1:].upper())
                rgb = _hex_rgb(value)
                luminance = _relative_luminance(rgb)
                cell.font = Font(color="FFFFFF" if luminance < 0.4 else "000000", bold=True)
        for ratio_cell in (row[3], row[4]):
            if isinstance(ratio_cell.value, (int, float)):
                ratio_cell.number_format = '0.00" : 1"'
    for row in palette_sheet.iter_rows(min_row=2):
        status = str(row[0].value).lower()
        status_fill = {
            "conforme": "E2F0D9",
            "error": "F4CCCC",
            "revision manual": "FFF2CC",
        }.get(status)
        if status_fill:
            row[0].fill = PatternFill("solid", fgColor=status_fill)
            row[0].font = Font(bold=True, color="404040")
        for column in (2, 3, 4):
            value = row[column - 1].value
            if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                cell = row[column - 1]
                cell.fill = PatternFill("solid", fgColor=value[1:].upper())
                luminance = _relative_luminance(_hex_rgb(value))
                cell.font = Font(color="FFFFFF" if luminance < 0.4 else "000000", bold=True)
        for ratio_cell in (row[4], row[5]):
            if isinstance(ratio_cell.value, (int, float)):
                ratio_cell.number_format = '0.00" : 1"'

    summary_sheet.sheet_view.showGridLines = False
    summary_sheet.column_dimensions["A"].width = 32
    summary_sheet.column_dimensions["B"].width = 22
    summary_sheet.column_dimensions["C"].width = 4
    summary_sheet.column_dimensions["D"].width = 20
    summary_sheet.column_dimensions["E"].width = 14
    summary_sheet.column_dimensions["F"].width = 14
    findings_widths = [15, 24, 42, 24, 70, 18, 18, 16, 17, 18, 22, 70, 42]
    for index, width in enumerate(findings_widths, start=1):
        findings.column_dimensions[chr(64 + index)].width = width
    contrast_widths = [70, 22, 20, 16, 20, 20, 85, 24, 58]
    for index, width in enumerate(contrast_widths, start=1):
        contrast_sheet.column_dimensions[chr(64 + index)].width = width
    palette_widths = [20, 75, 22, 22, 16, 18, 72]
    for index, width in enumerate(palette_widths, start=1):
        palette_sheet.column_dimensions[chr(64 + index)].width = width

    workbook.properties.title = _excel_value(title)
    workbook.properties.subject = "Resultados de auditoría automatizada de accesibilidad"
    workbook.properties.creator = "Web Accessibility Automation"
    workbook.save(path)


def save_reports(results, name, title=None):
    """Guarda <name>.json y <name>.html en la carpeta de reportes. Devuelve las rutas."""
    folder = Path(settings.REPORTS_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    base = safe_name(name)
    json_path = folder / f"{base}.json"
    html_path = folder / f"{base}.html"
    css_path = folder / f"{base}.suggestions.css"
    excel_path = folder / f"{base}.xlsx"
    recommendations = contrast_recommendations(results)
    color_audit = contrast_color_audit(results)
    json_path.write_text(json.dumps(
        {
            "summary": summarize(results),
            "violations": results.get("violations", []),
            "contrast_recommendations": recommendations,
            "contrast_color_audit": color_audit,
        },
        indent=2, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(
        build_html(results, title or name, export_filename=excel_path.name),
        encoding="utf-8",
    )
    css_path.write_text(build_contrast_css(results), encoding="utf-8")
    _write_excel_report(results, excel_path, title or name)
    return json_path, html_path
