from app.services.catalog import AUTO_STRATEGY
from app.services.generations.create_generation import Target

LAYOUT_OPTIONS = ("auto", "crop", "fit_blur", "split")


class BuildTargets:
    def execute(self, form: dict[str, list[str]]) -> list[Target]:
        targets = []
        for network in form.get("network", []):
            options: dict = {}
            layout = self._first(form, f"layout.{network}")
            if layout in LAYOUT_OPTIONS and layout != "auto":
                options["layout"] = layout
            subtitle = self._first(form, f"subtitle.{network}")
            if subtitle:
                options["subtitle_preset"] = subtitle
            if self._first(form, f"auto_approve.{network}"):
                options["auto_approve"] = True
            targets.append(Target(network=network, strategy=self._first(form, f"strategy.{network}") or AUTO_STRATEGY,
                                  options=options))
        return targets

    def _first(self, form: dict[str, list[str]], key: str) -> str:
        values = form.get(key) or [""]
        return values[0].strip()
