from dataclasses import dataclass

WIDTH, HEIGHT, FPS = 1080, 1920, 30
LAYOUTS = ("auto", "crop", "fit_blur", "split")


@dataclass
class FrameLayout:
    name: str
    video_filter: str
    caption_margin: int


class BuildFrameLayout:
    def execute(self, requested: str, options: dict, source_size: tuple[int, int]) -> FrameLayout:
        name = self._resolve(requested, source_size)
        tail = f"setsar=1,fps={FPS},format=yuv420p"
        if name == "crop":
            return FrameLayout(name, self._crop(float(options.get("crop_x", 0.5)), tail), 640)
        if name == "fit_blur":
            return FrameLayout(name, self._fit_blur(tail), 480)
        return self._split(options, source_size, tail)

    def _resolve(self, requested: str, source_size: tuple[int, int]) -> str:
        if requested in ("crop", "fit_blur", "split"):
            return requested
        width, height = source_size
        return "crop" if height >= width else "fit_blur"

    def _crop(self, crop_x: float, tail: str) -> str:
        return f"[0:v]scale=-2:{HEIGHT},crop={WIDTH}:{HEIGHT}:(iw-{WIDTH})*{crop_x:.3f}:0,{tail}[v]"

    def _fit_blur(self, tail: str) -> str:
        return (f"[0:v]split[a][b];"
                f"[a]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},"
                f"boxblur=25:2,eq=brightness=-0.10[bg];"
                f"[b]scale={WIDTH}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,{tail}[v]")

    def _split(self, options: dict, source_size: tuple[int, int], tail: str) -> FrameLayout:
        top = options.get("top_box") or [0.25, 0.0, 0.5, 1.0]
        bottom = options.get("bottom_box")
        if not bottom:
            raise ValueError("o layout split precisa de bottom_box [x, y, largura, altura]")
        source_width, source_height = source_size
        bottom_height = int(WIDTH * (bottom[3] * source_height) / (bottom[2] * source_width)) // 2 * 2
        bottom_height = max(600, min(1100, bottom_height))
        top_height = HEIGHT - bottom_height
        video_filter = (f"[0:v]split[a][b];"
                        f"[a]{self._box(top)},scale={WIDTH}:{top_height}:force_original_aspect_ratio=increase,"
                        f"crop={WIDTH}:{top_height}[t];"
                        f"[b]{self._box(bottom)},scale={WIDTH}:{bottom_height}:force_original_aspect_ratio=increase,"
                        f"crop={WIDTH}:{bottom_height}[d];"
                        f"[t][d]vstack,{tail}[v]")
        return FrameLayout("split", video_filter, max(0, HEIGHT - top_height - 45))

    def _box(self, box: list[float]) -> str:
        x, y, width, height = box
        return f"crop=iw*{width:.4f}:ih*{height:.4f}:iw*{x:.4f}:ih*{y:.4f}"
