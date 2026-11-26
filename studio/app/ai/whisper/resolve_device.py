class ResolveWhisperDevice:
    def execute(self, requested: str) -> str:
        if requested != "auto":
            return requested
        import ctranslate2
        try:
            return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except RuntimeError:
            return "cpu"
