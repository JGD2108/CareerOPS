from __future__ import annotations

import json
from typing import TypeVar

from openai import OpenAI
from pydantic import BaseModel

from app.config import get_settings


settings = get_settings()
SchemaModel = TypeVar("SchemaModel", bound=BaseModel)


def ai_agents_enabled() -> bool:
    return bool(settings.openai_api_key)


def require_ai_agents_enabled() -> None:
    if not ai_agents_enabled():
        raise ValueError("OPENAI_API_KEY is required to run LangGraph AI agents.")


def _client() -> OpenAI:
    require_ai_agents_enabled()
    return OpenAI(api_key=settings.openai_api_key)


def _strict_json_schema(schema: dict) -> dict:
    if not isinstance(schema, dict):
        return schema

    schema.pop("default", None)

    schema_type = schema.get("type")
    if schema_type == "object":
        schema["additionalProperties"] = False
        properties = schema.get("properties") or {}
        schema["required"] = list(properties.keys())
        for property_schema in properties.values():
            _strict_json_schema(property_schema)
    elif schema_type == "array" and "items" in schema:
        _strict_json_schema(schema["items"])

    for key in ("$defs", "definitions"):
        nested = schema.get(key) or {}
        for nested_schema in nested.values():
            _strict_json_schema(nested_schema)

    for key in ("anyOf", "oneOf", "allOf"):
        for nested_schema in schema.get(key) or []:
            _strict_json_schema(nested_schema)

    if "not" in schema and isinstance(schema["not"], dict):
        _strict_json_schema(schema["not"])

    return schema


def generate_structured_output(
    *,
    schema_model: type[SchemaModel],
    schema_name: str,
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
) -> SchemaModel:
    client = _client()
    strict_schema = _strict_json_schema(schema_model.model_json_schema())
    response = client.responses.create(
        model=model or settings.openai_model,
        input=[
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}],
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": strict_schema,
                "strict": True,
            }
        },
    )
    output_text = getattr(response, "output_text", None)
    if not output_text:
        raise ValueError("The AI model returned an empty structured response.")
    return schema_model.model_validate(json.loads(output_text))


def generate_embedding(text: str, *, model: str | None = None) -> list[float]:
    client = _client()
    response = client.embeddings.create(
        model=model or settings.openai_embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
    )
    if not response.data:
        raise ValueError("The embedding API returned no vectors.")
    return list(response.data[0].embedding)
