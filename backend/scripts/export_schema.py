"""Exporta o JSON Schema dos modelos da API para gerar os tipos TypeScript do frontend.

Uso: `uv run python -m scripts.export_schema <pasta-de-saída>`
(chamado por `npm run gen:types` no frontend).
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.models.document import Document
from app.models.job import Job

API_MODELS: dict[str, type[BaseModel]] = {"document": Document, "job": Job}


def _drop_property_titles(schema: dict[str, Any]) -> None:
    """Remove o título de cada propriedade (vira apelido inútil no TypeScript gerado)."""
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    for definition in schema.get("$defs", {}).values():
        _drop_property_titles(definition)


def build_schemas() -> dict[str, dict[str, Any]]:
    # Modo "serialization": descreve o JSON que a API devolve.
    schemas: dict[str, dict[str, Any]] = {}
    for name, model in API_MODELS.items():
        schema = model.model_json_schema(mode="serialization")
        _drop_property_titles(schema)
        schemas[name] = schema
    return schemas


def write_schemas(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, schema in build_schemas().items():
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("uso: python -m scripts.export_schema <pasta-de-saída>")
    write_schemas(Path(sys.argv[1]))
