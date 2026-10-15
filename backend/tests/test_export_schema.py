"""Exportação do JSON Schema que gera os tipos TypeScript do frontend."""

import json
from pathlib import Path

from scripts.export_schema import build_schemas, write_schemas


def test_exports_one_schema_per_api_model() -> None:
    schemas = build_schemas()

    assert set(schemas) == {"document", "job"}
    assert schemas["document"]["title"] == "Document"
    assert schemas["job"]["title"] == "Job"


def test_document_schema_carries_emphasis_and_alternatives() -> None:
    word = build_schemas()["document"]["$defs"]["Word"]["properties"]

    assert {"bold", "italic", "alternatives", "status"} <= set(word)


def test_enums_are_exported_as_string_values() -> None:
    status = build_schemas()["document"]["$defs"]["WordStatus"]

    assert status["enum"] == ["accepted", "resolved", "uncertain", "edited"]


def test_write_schemas_creates_json_files(tmp_path: Path) -> None:
    write_schemas(tmp_path)

    assert json.loads((tmp_path / "document.schema.json").read_text())["title"] == "Document"
    assert json.loads((tmp_path / "job.schema.json").read_text())["title"] == "Job"


def test_fields_with_defaults_are_required_in_api_output() -> None:
    # A API sempre devolve esses campos preenchidos; o frontend não deve tratá-los como opcionais.
    word = build_schemas()["document"]["$defs"]["Word"]

    assert {"bold", "italic", "alternatives", "resolved_by"} <= set(word["required"])


def test_properties_have_no_titles() -> None:
    # Títulos por propriedade viram apelidos inúteis (Id1, Text1...) no TypeScript gerado.
    word = build_schemas()["document"]["$defs"]["Word"]["properties"]

    assert all("title" not in prop for prop in word.values())


def test_frontend_schema_is_up_to_date() -> None:
    # Se falhar: os modelos mudaram e faltou rodar `npm run gen:types` no frontend.
    schema_dir = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "types" / "schema"

    for name, schema in build_schemas().items():
        committed = json.loads((schema_dir / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert committed == schema, f"{name}.schema.json desatualizado: rode npm run gen:types"
