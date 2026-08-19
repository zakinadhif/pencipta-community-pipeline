import unittest
from agent.tools import SafeMath
from db.vector import EMBEDDING_DIMENSIONS

class AgentToolTests(unittest.TestCase):
    def test_safe_math_supports_basic_arithmetic(self) -> None:
        self.assertEqual(SafeMath.calculate("(18 * 4) / 3"), 24)

    def test_safe_math_rejects_python_expressions(self) -> None:
        with self.assertRaises(ValueError):
            SafeMath.calculate("__import__('os').system('echo unsafe')")

    def test_embedding_dimension_is_declared_for_schema_compatibility(self) -> None:
        self.assertEqual(EMBEDDING_DIMENSIONS, 1536)
