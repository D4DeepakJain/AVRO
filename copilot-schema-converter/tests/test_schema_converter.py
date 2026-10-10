import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "tools" / "schema_converter.py"
spec = importlib.util.spec_from_file_location("schema_converter", SCRIPT)
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


class SchemaConverterTests(unittest.TestCase):
    def test_infer_types(self):
        self.assertEqual(converter.infer_type("abc"), "string")
        self.assertEqual(converter.infer_type(42), "int")
        self.assertEqual(converter.infer_type(True), "boolean")
        self.assertEqual(converter.infer_type({"x": 1}), "record")
        self.assertEqual(converter.infer_type([1, 2]), "array")

    def test_add_delete_modify_diff(self):
        old = {"id": "null | string", "age": "null | int", "email": "null | string"}
        new = {"id": "null | string", "age": "null | string", "phone": "null | string"}
        diff = converter.changes(old, new)
        self.assertEqual([x["field"] for x in diff["added"]], ["phone"])
        self.assertEqual([x["field"] for x in diff["deleted"]], ["email"])
        self.assertEqual([x["field"] for x in diff["modified"]], ["age"])
        self.assertEqual([x["field"] for x in diff["unchanged"]], ["id"])

    def test_generated_avsc_is_valid_json(self):
        schema = converter.build_record({"id": "101", "active": True}, "User", "com.example")
        parsed = json.loads(json.dumps(schema))
        self.assertEqual(parsed["name"], "User")
        self.assertEqual(len(parsed["fields"]), 2)

    def test_java_has_getter_setter(self):
        java = converter.generate_java({"id": "101"}, "User", "com.example")
        self.assertIn("private String id;", java)
        self.assertIn("getId()", java)
        self.assertIn("setId(String id)", java)


if __name__ == "__main__":
    unittest.main()
