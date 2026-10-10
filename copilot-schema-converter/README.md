# GitHub Copilot Schema Converter (Java + JSON + AVSC)

This repository template configures a GitHub Copilot custom agent and includes a deterministic Python utility that generates:
- a Java POJO (`<ClassName>.java`)
- an Avro schema (`<ClassName>.avsc`)
- a Markdown schema change report (`<ClassName>-schema-change-report.md`)

## Requirements
- VS Code with GitHub Copilot Chat and custom agents enabled
- Python 3.9+ (standard library only)
- A repository opened as the VS Code workspace

## Setup
1. Copy `.github/agents/schema-converter.agent.md` and `.github/copilot-instructions.md` into your repository.
2. Copy `tools/schema_converter.py` into the repository's `tools/` directory.
3. Put a complete JSON record in a file, for example `examples/user.json`.
4. In VS Code Copilot Chat, select Agent mode and invoke **Schema Converter**, or ask Copilot to convert the JSON payload.

## Run directly
```bash
python3 tools/schema_converter.py \
  --input examples/user.json \
  --class-name User \
  --output-dir generated \
  --package com.example.models
```

Outputs:
- `generated/User.java`
- `generated/User.avsc`
- `generated/User-schema-change-report.md`

## Change detection
The existing AVSC at the output path is the baseline. Run once to establish a baseline, edit the JSON payload, then run again. The report will show additions (+), deletions (-), modifications (~), and unchanged fields.

**Important:** The utility treats the JSON as a complete schema snapshot. A missing field is considered deleted. Do not use a partial event payload to update a schema unless that is explicitly intended.

## Type inference limitations
A JSON instance is not a complete schema contract. For example, `{"amount": 12}` alone cannot tell whether `amount` should be an Avro `int`, `long`, decimal, or nullable field in the actual application. This starter utility infers types from sample values and emits nullable Avro fields with a null default. Review the schema before using it in production. For fields whose sample value is `null`, the starter defaults to nullable string because the intended type cannot be inferred from null alone.

Nested objects are emitted as Avro records. Java nested values are represented as `Map<String, Object>` and arrays as `List<Object>` in this starter implementation. Extend this mapping if you need strongly typed nested Java classes.

## Tests
```bash
python3 -m unittest discover -s tests -v
```

## Notes
- The utility validates JSON parsing and generated AVSC JSON syntax, but does not run the Avro compiler or compile Java.
- Type changes and deletions may be breaking. Review the generated report before committing.
- Keep generated output in version control if you want the prior AVSC to serve as the next run's baseline.
