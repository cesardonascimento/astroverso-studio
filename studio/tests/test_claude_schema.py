from pydantic import BaseModel

from app.ai.claude import BuildStrictSchema


class Child(BaseModel):
    title: str
    default: int = 1


class Parent(BaseModel):
    name: str
    children: list[Child]


def test_schema_closes_objects_and_keeps_field_names():
    schema = BuildStrictSchema().execute(Parent)
    child = schema["$defs"]["Child"]
    assert schema["additionalProperties"] is False
    assert child["required"] == ["title", "default"]
    assert set(child["properties"]) == {"title", "default"}
    assert "title" not in schema
