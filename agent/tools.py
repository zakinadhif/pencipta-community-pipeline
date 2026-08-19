"""Narrow deterministic tools exposed to the single agent."""
from __future__ import annotations
import ast
import operator
from datetime import UTC, datetime
from agents import function_tool

class SafeMath:
    binary_ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod}
    unary_ops = {ast.UAdd: operator.pos, ast.USub: operator.neg}
    @classmethod
    def calculate(cls, expression: str) -> float:
        def visit(node: ast.AST) -> float:
            if isinstance(node, ast.Expression): return visit(node.body)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool): return float(node.value)
            if isinstance(node, ast.BinOp) and type(node.op) in cls.binary_ops: return cls.binary_ops[type(node.op)](visit(node.left), visit(node.right))
            if isinstance(node, ast.UnaryOp) and type(node.op) in cls.unary_ops: return cls.unary_ops[type(node.op)](visit(node.operand))
            raise ValueError("Only numeric arithmetic is allowed.")
        return visit(ast.parse(expression, mode="eval"))

@function_tool
def calculate(expression: str) -> str:
    """Evaluate a basic numeric arithmetic expression, such as ``(18 * 4) / 3``."""
    try: return str(SafeMath.calculate(expression))
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError) as error: return f"Calculation error: {error}"

@function_tool
def get_current_utc_time() -> str:
    """Return the current UTC time in ISO-8601 format."""
    return datetime.now(UTC).isoformat()
