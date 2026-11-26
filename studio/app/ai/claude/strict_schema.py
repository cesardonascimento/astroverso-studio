import copy
from typing import Any

from pydantic import BaseModel


class BuildStrictSchema:
    def execute(self, model: type[BaseModel]) -> dict[str, Any]:
        schema = copy.deepcopy(model.model_json_schema())
        self._walk(schema)
        return schema

    def _walk(self, node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                self._walk(item)
            return
        if not isinstance(node, dict):
            return
        node.pop("title", None)
        node.pop("default", None)
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])
            for prop in node["properties"].values():
                self._walk(prop)
        for key, value in node.items():
            if key != "properties":
                self._walk(value)
