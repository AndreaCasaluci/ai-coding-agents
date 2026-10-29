import unittest

from mini_agent.tools import ToolRegistry, tool


@tool
def add(a: int, b: int = 1) -> int:
    """Add two numbers."""
    return a + b


@tool(name="boom", side_effect=True)
def boom() -> str:
    """Always fails."""
    raise RuntimeError("kaboom")


class ToolTests(unittest.TestCase):
    def test_schema_derived_from_signature(self):
        schema = add.schema()
        self.assertEqual(schema["name"], "add")
        self.assertEqual(schema["description"], "Add two numbers.")
        self.assertEqual(schema["parameters"]["properties"]["a"]["type"], "integer")
        self.assertEqual(schema["parameters"]["required"], ["a"])
        self.assertEqual(schema["parameters"]["properties"]["b"]["default"], 1)

    def test_dispatch_success(self):
        reg = ToolRegistry([add])
        result = reg.dispatch("add", {"a": 2, "b": 3})
        self.assertTrue(result.ok)
        self.assertEqual(result.content, "5")

    def test_unknown_tool_is_data_not_exception(self):
        reg = ToolRegistry([add])
        result = reg.dispatch("nope", {})
        self.assertFalse(result.ok)
        self.assertIn("Unknown tool", result.content)

    def test_bad_arguments_are_reported(self):
        reg = ToolRegistry([add])
        result = reg.dispatch("add", {"wrong": 1})
        self.assertFalse(result.ok)
        self.assertIn("Invalid arguments", result.content)

    def test_tool_exception_is_contained(self):
        reg = ToolRegistry([boom])
        result = reg.dispatch("boom", {})
        self.assertFalse(result.ok)
        self.assertIn("kaboom", result.content)

    def test_malformed_json_arguments(self):
        reg = ToolRegistry([add])
        result = reg.dispatch("add", {"__parse_error__": "{not json"})
        self.assertFalse(result.ok)
        self.assertIn("parse", result.content.lower())

    def test_duplicate_registration_rejected(self):
        reg = ToolRegistry([add])
        with self.assertRaises(ValueError):
            reg.register(add)


if __name__ == "__main__":
    unittest.main()
