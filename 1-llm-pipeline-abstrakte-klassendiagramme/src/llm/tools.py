from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, get_type_hints


_PY_TO_JSON: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
}


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON-Schema-Objekt für die Argumente
    fn: Callable[..., Any]

    def to_litellm(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def invoke(self, arguments: dict[str, Any]) -> Any:
        return self.fn(**arguments)


def make_tool(
    fn: Callable[..., Any],
    description: str = "",
    parameters: dict | None = None,
) -> Tool:
    """Baut aus einer Python-Funktion ein Tool. Das JSON-Schema wird aus den Typannotationen abgeleitet."""
    name = fn.__name__
    doc = description or (inspect.getdoc(fn) or "")
    params = parameters if parameters is not None else _infer_parameters(fn)
    return Tool(name=name, description=doc, parameters=params, fn=fn)


def _infer_parameters(fn: Callable[..., Any]) -> dict:
    sig = inspect.signature(fn)
    hints: dict[str, Any] = {}
    try:
        hints = get_type_hints(fn)
    except Exception:
        pass

    props: dict[str, dict] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        hint = hints.get(pname)
        props[pname] = {"type": _hint_to_json_type(hint)}
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    schema: dict = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


def _hint_to_json_type(hint: Any) -> str:
    if hint is None:
        return "string"
    origin = getattr(hint, "__origin__", None)
    if origin is list:
        return "array"
    if origin is dict:
        return "object"
    name = getattr(hint, "__name__", None) or ""
    return _PY_TO_JSON.get(name, "string")
