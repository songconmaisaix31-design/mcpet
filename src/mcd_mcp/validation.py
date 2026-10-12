"""Shared payload validation; no model or GUI imports."""
from typing import Any

def validate_arguments(arguments: Any, schema: dict[str, Any]) -> None:
    """校验工具 payload，不把坏 JSON、缺字段或未知字段默默变成写请求。"""
    kind = schema.get("type")
    checks = {"object": lambda v: isinstance(v, dict),
              "array": lambda v: isinstance(v, list),
              "string": lambda v: isinstance(v, str),
              "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
              "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
              "boolean": lambda v: isinstance(v, bool)}
    if kind in checks and not checks[kind](arguments):
        raise ValueError("工具参数类型不正确")
    if "enum" in schema and arguments not in schema["enum"]:
        raise ValueError("工具参数不在允许值中")
    if isinstance(arguments, dict):
        props = schema.get("properties", {})
        if set(schema.get("required", [])) - set(arguments):
            raise ValueError("工具参数缺少必填字段")
        if set(arguments) - set(props):
            raise ValueError("工具参数含未知字段")
        for key, value in arguments.items():
            validate_arguments(value, props[key])
    if isinstance(arguments, list) and "items" in schema:
        for value in arguments:
            validate_arguments(value, schema["items"])

