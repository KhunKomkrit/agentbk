"""Built-in tools — get_datetime, calculate, get_weather (wttr.in)."""
from __future__ import annotations
import ast
import asyncio
import datetime
import operator
from typing import Any

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_datetime",
            "description": "Get current date and time in Thai timezone (Asia/Bangkok, UTC+7).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": (
                "Evaluate a safe arithmetic expression. "
                "Supports +, -, *, /, //, %, ** and parentheses. "
                "Numbers and operators only."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Math expression, e.g. '(2 + 3) * 4'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city using wttr.in (no API key needed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name in English or Thai"}
                },
                "required": ["city"],
            },
        },
    },
]


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch tool call by name. Always returns a string result."""
    if name == "get_datetime":
        return _get_datetime()
    if name == "calculate":
        return _calculate(arguments.get("expression", ""))
    if name == "get_weather":
        return await _get_weather_async(arguments.get("city", ""))
    return f"Unknown tool: {name}"


# ── implementations ───────────────────────────────────────────────────────────

def _get_datetime() -> str:
    tz  = datetime.timezone(datetime.timedelta(hours=7))
    now = datetime.datetime.now(tz=tz)
    return now.strftime("%A, %d %B %Y  %H:%M:%S (ICT / UTC+7)")


_SAFE_NODES = {
    ast.Expression, ast.BinOp,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.UAdd, ast.USub, ast.UnaryOp,
    ast.Constant,
}
_OPS = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:      operator.mod,
    ast.Pow:      operator.pow,
    ast.UAdd:     operator.pos,
    ast.USub:     operator.neg,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError(f"Disallowed node: {type(node).__name__}")


def _calculate(expression: str) -> str:
    expression = expression.strip()
    if not expression:
        return "Error: empty expression"
    try:
        tree = ast.parse(expression, mode="eval")
        for node in ast.walk(tree):
            if type(node) not in _SAFE_NODES:
                return f"Error: disallowed operation ({type(node).__name__})"
        result = _eval_node(tree)
        return str(int(result)) if result == int(result) else f"{result:.6g}"
    except Exception as exc:
        return f"Error: {exc}"


async def _get_weather_async(city: str) -> str:
    city = city.strip()
    if not city:
        return "Error: city name is required"
    try:
        import httpx
        url = f"https://wttr.in/{city}?format=j1"
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url, headers={"Accept": "application/json",
                                               "User-Agent": "AgentBK/1.0"})
            r.raise_for_status()
            data = r.json()
        cur      = data["current_condition"][0]
        temp_c   = cur["temp_C"]
        feels    = cur["FeelsLikeC"]
        desc     = cur["weatherDesc"][0]["value"]
        humidity = cur["humidity"]
        wind     = cur["windspeedKmph"]
        wind_dir = cur["winddir16Point"]
        return (
            f"Weather in {city}: {desc}, {temp_c}°C "
            f"(feels like {feels}°C), humidity {humidity}%, "
            f"wind {wind} km/h {wind_dir}."
        )
    except Exception as exc:
        return f"Weather lookup failed: {exc}"
