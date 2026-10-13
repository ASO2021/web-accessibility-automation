import ast
import math
import operator
import re
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


GAME_PATH = Path(__file__).resolve().parents[1] / "math_game" / "index.html"


def _solve(question):
    expression = question.removesuffix(" = ?")
    expression = expression.replace("×", "*").replace("÷", "/").replace("−", "-")
    expression = re.sub(
        r"(\d+|\))²",
        lambda match: (
            f"{match.group(1)} ** 2"
            if match.group(1) == ")"
            else f"({match.group(1)} ** 2)"
        ),
        expression,
    )
    expression = re.sub(r"(\d+)³", r"(\1 ** 3)", expression)
    expression = re.sub(r"√\((\d+)\)", r"sqrt(\1)", expression)

    operations = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.floordiv,
        ast.Pow: operator.pow,
    }

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sqrt"
            and len(node.args) == 1
        ):
            return math.isqrt(evaluate(node.args[0]))
        raise ValueError(f"Unsupported math expression: {question}")

    result = evaluate(ast.parse(expression, mode="eval"))
    assert isinstance(result, int)
    return result


@pytest.mark.functional
def test_correct_answer_increases_score_and_streak():
    """The game accepts a correct answer and updates score and progress."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(GAME_PATH.as_uri())
            page.get_by_role("button", name="Empezar juego").click()
            question = page.locator("#question").inner_text()
            assert any(symbol in question for symbol in ("(", "²", "³", "√", "×"))
            answer = _solve(question)
            page.get_by_label("Tu respuesta").fill(str(answer))
            page.get_by_role("button", name="Responder").click()

            assert page.locator("#score").inner_text() == "10"
            assert page.locator("#streak").inner_text() == "1"
            assert page.locator("#progress").inner_text() == "1/10"
            assert page.locator("#progress-bar").get_attribute("value") == "1"
            assert "¡Correcto!" in page.get_by_role("status").inner_text()
        finally:
            browser.close()


@pytest.mark.functional
def test_trophy_appears_when_second_round_time_runs_out():
    """The game shows the trophy when time runs out in round two."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.clock.install()
            page.goto(GAME_PATH.as_uri())
            page.get_by_role("button", name="Empezar juego").click()
            for _ in range(10):
                answer = _solve(page.locator("#question").inner_text())
                page.get_by_label("Tu respuesta").fill(str(answer))
                page.get_by_role("button", name="Responder").click()
            assert page.locator("#round-label").inner_text() == "Ronda 2 · Más difícil"
            page.clock.run_for(50_000)
            assert page.locator("#time").inner_text() == "10"
            assert "is-urgent" in page.locator("#timer-stat").get_attribute("class")
            page.clock.run_for(60_000)

            assert page.get_by_role("img", name="Trofeo por completar la partida").is_visible()
            assert "Se acabó el tiempo" in page.get_by_role("status").inner_text()
        finally:
            browser.close()


@pytest.mark.functional
def test_completing_first_round_starts_second_round():
    """Ten answers complete round one and unlock the timed harder round."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(GAME_PATH.as_uri())
            page.get_by_role("button", name="Empezar juego").click()
            for index in range(1, 11):
                answer = _solve(page.locator("#question").inner_text())
                page.get_by_label("Tu respuesta").fill(str(answer))
                page.get_by_role("button", name="Responder").click()
                if index < 10:
                    assert page.locator("#progress").inner_text() == f"{index}/10"

            assert page.locator("#round-label").inner_text() == "Ronda 2 · Más difícil"
            assert page.locator("#progress").inner_text() == "0/10"
            assert page.locator("#time").inner_text() == "60"
            assert "¡Maravilloso!" in page.get_by_role("status").inner_text()
            assert "10/10" in page.get_by_role("status").inner_text()
        finally:
            browser.close()


@pytest.mark.functional
def test_home_button_returns_to_initial_screen_and_stops_timer():
    """The home button resets the game and stops the round timer."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.clock.install()
            page.goto(GAME_PATH.as_uri())
            page.get_by_role("button", name="Empezar juego").click()
            for _ in range(10):
                answer = _solve(page.locator("#question").inner_text())
                page.get_by_label("Tu respuesta").fill(str(answer))
                page.get_by_role("button", name="Responder").click()

            page.clock.run_for(3_000)
            assert page.locator("#time").inner_text() == "57"
            page.get_by_role("button", name="Volver al inicio").click()

            assert page.locator("#question").inner_text() == "¿Listo?"
            assert page.locator("#round-label").inner_text() == "Ronda 1"
            assert page.locator("#progress").inner_text() == "0/10"
            assert page.locator("#score").inner_text() == "0"
            assert page.locator("#time").inner_text() == "—"
            assert page.get_by_role("button", name="Empezar juego").is_enabled()
            assert page.get_by_role("button", name="Volver al inicio").is_hidden()
            page.clock.run_for(5_000)
            assert page.locator("#time").inner_text() == "—"
        finally:
            browser.close()


@pytest.mark.functional
def test_completing_both_rounds_shows_final_trophy():
    """The player can finish all 20 challenges and see a final celebration."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(GAME_PATH.as_uri())
            page.get_by_role("button", name="Empezar juego").click()

            for _ in range(20):
                answer = _solve(page.locator("#question").inner_text())
                page.get_by_label("Tu respuesta").fill(str(answer))
                page.get_by_role("button", name="Responder").click()

            assert page.locator("#progress").inner_text() == "10/10"
            assert page.locator("#progress-bar").get_attribute("value") == "10"
            assert page.get_by_role("img", name="Trofeo por completar la partida").is_visible()
            assert "¡Maravilloso!" in page.get_by_role("status").inner_text()
            assert page.get_by_role("button", name="Jugar otra vez").is_enabled()
        finally:
            browser.close()
