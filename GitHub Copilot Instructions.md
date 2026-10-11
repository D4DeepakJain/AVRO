# GitHub Copilot Instructions

## Schema Conversion Workflow

When asked to convert a JSON payload into a Java Model Class and an Avro schema (`.avsc`), follow the repository's Schema Converter workflow.

- Use the **Schema Converter** custom agent defined in `.github/agents/schema-converter.agent.md` when custom-agent delegation or selection is supported.
- If the custom agent is unavailable, perform the same workflow directly using the available Copilot tools.
- Do not require Python or a separate conversion script.
- Inspect existing Java classes and AVSC files before making changes.
- Use the existing AVSC as the baseline for detecting schema changes.
- Generate or update the Java Model Class and AVSC consistently from the same interpreted schema.
- Identify added, deleted, modified, and unchanged attributes.
- Treat missing attributes as deletions only when the input represents a complete schema snapshot.
- Flag potentially breaking changes, including deleted fields and incompatible type changes.
- Generate a Markdown change report containing the change summary, attribute-level details, generated file paths, and validation results.
- Validate files using available project tools. Clearly distinguish checks that were executed from checks that could not be performed.
- Preserve existing project conventions, package names, naming standards, and unrelated code.

## Default Output Locations

If the repository does not specify different locations, use:

- Java Model Class: `generated/<ClassName>.java`
- Avro schema: `schemas/<ClassName>.avsc`
- Change report: `reports/<ClassName>-schema-change-report.md`

## Schema Accuracy

Do not silently infer uncertain types or nullability. JSON samples may not represent every possible value. Ask for clarification when a reliable schema cannot be determined, and document any assumptions made.

## Completion Summary

After processing, summarize the files created or updated, the detected schema changes, and the validation status.