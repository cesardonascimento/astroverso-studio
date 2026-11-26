from app.services.catalog import Network

LAYOUT_OPTION_KEYS = ("crop_x", "top_box", "bottom_box")


class ResolveRenderSettings:
    def execute(self, network: Network, options: dict, plan: dict) -> dict:
        choice = plan.get("render") or {}
        settings = {"layout": options.get("layout") or network.layout or "auto",
                    "subtitle_preset": options.get("subtitle_preset") or network.subtitle_preset,
                    **{key: options[key] for key in LAYOUT_OPTION_KEYS if options.get(key) is not None}}
        if choice.get("layout"):
            settings["layout"] = choice["layout"]
        if choice.get("subtitle_preset"):
            settings["subtitle_preset"] = choice["subtitle_preset"]
        if (choice.get("crop_x") if choice.get("crop_x") is not None else -1) >= 0:
            settings["crop_x"] = choice["crop_x"]
        return settings
