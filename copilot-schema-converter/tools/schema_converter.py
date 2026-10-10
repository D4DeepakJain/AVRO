#!/usr/bin/env python3
"""Generate a Java POJO, Avro AVSC, and schema-change report from a JSON record."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PRIMITIVES = (str, int, float, bool, type(None))


def avro_name(name: str) -> str:
    """Return a legal Avro name, retaining a readable approximation."""
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not cleaned or not re.match(r"[A-Za-z_]", cleaned):
        cleaned = "_" + cleaned
    return cleaned


def java_identifier(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_$]", "_", name)
    if not cleaned or not re.match(r"[A-Za-z_$]", cleaned):
        cleaned = "_" + cleaned
    if cleaned in {
        "abstract", "assert", "boolean", "break", "byte", "case", "catch",
        "char", "class", "const", "continue", "default", "do", "double",
        "else", "enum", "extends", "final", "finally", "float", "for",
        "goto", "if", "implements", "import", "instanceof", "int",
        "interface", "long", "native", "new", "package", "private",
        "protected", "public", "return", "short", "static", "strictfp",
        "super", "switch", "synchronized", "this", "throw", "throws",
        "transient", "try", "void", "volatile", "while", "true", "false",
        "null", "_",
    }:
        cleaned += "_"
    return cleaned


def merge_types(values: list[Any]) -> str:
    types = {infer_type(v) for v in values}
    types.discard("null")
    if not types:
        return "null"
    if len(types) == 1:
        return next(iter(types))
    if types <= {"int", "long", "float", "double"}:
        if "double" in types or "float" in types:
            return "double"
        if "long" in types:
            return "long"
        return "int"
    # Heterogeneous arrays are represented as an Avro union when possible.
    return "union:" + ",".join(sorted(types))


def infer_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "int" if -(2**31) <= value < 2**31 else "long"
    if isinstance(value, float):
        return "double"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "record"
    if isinstance(value, list):
        return "array"
    return "string"


def avro_type(value: Any, field_name: str, namespace: str) -> Any:
    if value is None:
        return ["null", "string"]
    if isinstance(value, bool):
        return ["null", "boolean"]
    if isinstance(value, int):
        t = "int" if -(2**31) <= value < 2**31 else "long"
        return ["null", t]
    if isinstance(value, float):
        return ["null", "double"]
    if isinstance(value, str):
        return ["null", "string"]
    if isinstance(value, dict):
        return ["null", build_record(value, field_name.title().replace("_", ""), namespace)]
    if isinstance(value, list):
        non_null = [v for v in value if v is not None]
        if not non_null:
            item_type = "string"
        else:
            item_type = avro_type(non_null[0], field_name.title().replace("_", "") + "Item", namespace)
            if isinstance(item_type, list) and item_type and item_type[0] == "null":
                item_type = item_type[1]
        return ["null", {"type": "array", "items": item_type}]
    return ["null", "string"]


def build_record(obj: dict[str, Any], record_name: str, namespace: str) -> dict[str, Any]:
    fields = []
    for name, value in obj.items():
        fields.append({
            "name": avro_name(name),
            "type": avro_type(value, name, namespace),
            "default": None,
        })
    return {
        "type": "record",
        "name": avro_name(record_name),
        "namespace": namespace,
        "fields": fields,
    }


def java_type(value: Any) -> str:
    if value is None:
        return "String"
    if isinstance(value, bool):
        return "Boolean"
    if isinstance(value, int):
        return "Integer" if -(2**31) <= value < 2**31 else "Long"
    if isinstance(value, float):
        return "Double"
    if isinstance(value, str):
        return "String"
    if isinstance(value, dict):
        return "java.util.Map<String, Object>"
    if isinstance(value, list):
        return "java.util.List<Object>"
    return "Object"


def java_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def generate_java(obj: dict[str, Any], class_name: str, package: str | None) -> str:
    lines = []
    if package:
        lines += [f"package {package};", ""]
    lines += ["import java.util.List;", "import java.util.Map;", "", f"public class {java_identifier(class_name)} {{"]

    # Avoid emitting duplicate members if two JSON keys sanitize to the same identifier.
    used: set[str] = set()
    fields: list[tuple[str, str, str]] = []
    for json_name, value in obj.items():
        field = java_identifier(json_name)
        if field in used:
            raise ValueError(f"JSON field names collide after Java identifier conversion: {json_name!r} -> {field!r}")
        used.add(field)
        fields.append((json_name, field, java_type(value)))
        lines.append(f"    private {java_type(value)} {field};")
    if fields:
        lines.append("")
    lines += [f"    public {java_identifier(class_name)}() {{", "    }", ""]
    for json_name, field, typ in fields:
        cap = field[0].upper() + field[1:]
        lines += [
            f"    public {typ} get{cap}() {{",
            f"        return {field};",
            "    }",
            "",
            f"    public void set{cap}({typ} {field}) {{",
            f"        this.{field} = {field};",
            "    }",
            "",
        ]
    if lines and lines[-1] == "":
        lines.pop()
    lines.append("}")
    return "\n".join(lines) + "\n"


def avro_fields(schema: dict[str, Any], prefix: str = "") -> dict[str, str]:
    result = {}
    for field in schema.get("fields", []):
        name = field["name"]
        path = f"{prefix}.{name}" if prefix else name
        result[path] = type_label(field.get("type"))
    return result


def type_label(t: Any) -> str:
    if isinstance(t, list):
        return " | ".join(type_label(x) for x in t)
    if isinstance(t, dict):
        if t.get("type") == "array":
            return f"array<{type_label(t.get('items'))}>"
        if t.get("type") == "record":
            return "record"
        return str(t.get("type", "unknown"))
    return str(t)


def changes(old: dict[str, str], new: dict[str, str]) -> dict[str, list[dict[str, str]]]:
    old_keys, new_keys = set(old), set(new)
    added = [{"field": k, "new_type": new[k]} for k in sorted(new_keys - old_keys)]
    deleted = [{"field": k, "old_type": old[k]} for k in sorted(old_keys - new_keys)]
    modified = [
        {"field": k, "old_type": old[k], "new_type": new[k]}
        for k in sorted(old_keys & new_keys) if old[k] != new[k]
    ]
    unchanged = [{"field": k, "type": new[k]} for k in sorted(old_keys & new_keys) if old[k] == new[k]]
    return {"added": added, "deleted": deleted, "modified": modified, "unchanged": unchanged}


def render_report(class_name: str, input_path: Path, baseline_exists: bool,
                  diff: dict[str, list[dict[str, str]]], validation: list[str]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Schema Change Report — {class_name}", "",
        f"- Generated: {now}",
        f"- Input: `{input_path}`",
        f"- Baseline AVSC found: {'yes' if baseline_exists else 'no (initial generation)'}",
        f"- Added: **{len(diff['added'])}**",
        f"- Deleted: **{len(diff['deleted'])}**",
        f"- Modified: **{len(diff['modified'])}**",
        f"- Unchanged: **{len(diff['unchanged'])}**", "",
    ]
    for title, key, sign in [
        ("Added Attributes", "added", "+"),
        ("Deleted Attributes", "deleted", "-"),
        ("Modified Attributes", "modified", "~"),
        ("Unchanged Attributes", "unchanged", "="),
    ]:
        lines += [f"## {title}", ""]
        if not diff[key]:
            lines += ["None.", ""]
            continue
        for item in diff[key]:
            if key == "added":
                lines.append(f"- `{sign} {item['field']}` — {item['new_type']}")
            elif key == "deleted":
                lines.append(f"- `{sign} {item['field']}` — previous type: {item['old_type']} (potentially breaking)")
            elif key == "modified":
                lines.append(f"- `{sign} {item['field']}` — {item['old_type']} → {item['new_type']} (review compatibility)")
            else:
                lines.append(f"- `{item['field']}` — {item['type']}")
        lines.append("")
    lines += ["## Validation Results", ""]
    lines += [f"- {v}" for v in validation]
    lines += [""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to a complete JSON object payload")
    parser.add_argument("--class-name", required=True, help="Java class and AVSC record name")
    parser.add_argument("--output-dir", default="generated", help="Output directory (default: generated)")
    parser.add_argument("--package", default=None, help="Optional Java package, e.g. com.example.models")
    parser.add_argument("--namespace", default=None, help="Avro namespace (defaults to --package or com.example)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    if not input_path.is_file():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 2
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"ERROR: invalid JSON input: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("ERROR: top-level JSON value must be an object/record.", file=sys.stderr)
        return 2

    class_name = java_identifier(args.class_name)
    namespace = args.namespace or args.package or "com.example"
    output_dir.mkdir(parents=True, exist_ok=True)
    java_path = output_dir / f"{class_name}.java"
    avsc_path = output_dir / f"{class_name}.avsc"
    report_path = output_dir / f"{class_name}-schema-change-report.md"

    baseline_exists = avsc_path.is_file()
    old_fields: dict[str, str] = {}
    if baseline_exists:
        try:
            baseline = json.loads(avsc_path.read_text(encoding="utf-8"))
            old_fields = avro_fields(baseline)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            print(f"ERROR: existing AVSC baseline is invalid; refusing to overwrite: {exc}", file=sys.stderr)
            return 2

    try:
        schema = build_record(payload, class_name, namespace)
        java_source = generate_java(payload, class_name, args.package)
        new_fields = avro_fields(schema)
        diff = changes(old_fields, new_fields)
        # Parse generated AVSC back before writing any output.
        avsc_text = json.dumps(schema, indent=2, ensure_ascii=False) + "\n"
        json.loads(avsc_text)
    except (ValueError, TypeError) as exc:
        print(f"ERROR: could not generate schema: {exc}", file=sys.stderr)
        return 2

    validation = [
        "Input JSON parsed successfully.",
        "Top-level payload is a JSON object.",
        "Generated AVSC is valid JSON.",
        "Java source generated; compilation has not been run by this utility.",
    ]
    # Write temporary files first, then replace output files.
    temp_java = java_path.with_suffix(".java.tmp")
    temp_avsc = avsc_path.with_suffix(".avsc.tmp")
    temp_report = report_path.with_suffix(".md.tmp")
    report = render_report(class_name, input_path, baseline_exists, diff, validation)
    try:
        temp_java.write_text(java_source, encoding="utf-8")
        temp_avsc.write_text(avsc_text, encoding="utf-8")
        temp_report.write_text(report, encoding="utf-8")
        temp_java.replace(java_path)
        temp_avsc.replace(avsc_path)
        temp_report.replace(report_path)
    except OSError as exc:
        for p in (temp_java, temp_avsc, temp_report):
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass
        print(f"ERROR: failed to write generated files: {exc}", file=sys.stderr)
        return 2

    print("Schema conversion completed.")
    print(f"Java:   {java_path}")
    print(f"AVSC:   {avsc_path}")
    print(f"Report: {report_path}")
    print(f"Changes: +{len(diff['added'])} / -{len(diff['deleted'])} / ~{len(diff['modified'])} / ={len(diff['unchanged'])}")
    if not baseline_exists:
        print("NOTE: no previous AVSC baseline existed; this run establishes the baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
