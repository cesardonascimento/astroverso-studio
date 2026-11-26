from app.models import Generation, GenerationState, Output, OutputState, OutputVersion, VersionKind

PLAN = {"strategy": "viral", "title": "Título", "hook_text": "olha isso", "caption": "legenda", "hashtags": ["a", "b"],
        "why": "porque", "alternatives": [], "changes": "", "render": {"layout": "", "subtitle_preset": "", "crop_x": -1},
        "duration_s": 8.7,
        "segments": [{"start": 1.9, "end": 6.25, "purpose": "gancho", "text_start": 2.0, "text_end": 6.0, "text": "a b"},
                     {"start": 9.9, "end": 14.25, "purpose": "payoff", "text_start": 10.0, "text_end": 14.0, "text": "c d"}]}


def awaiting_approval(session, instance: str = "a") -> Output:
    generation = Generation(instance=instance, algorithm="corte", inputs={"url": "x"}, title="Vídeo",
                            state=GenerationState.READY, source={"duration_s": 20})
    output = Output(network="tiktok", strategy="auto", state=OutputState.AWAITING_APPROVAL, current_version=1)
    output.versions.append(OutputVersion(version=1, kind=VersionKind.INITIAL, plan=PLAN, strategy_name="viral",
                                         strategy_text="texto"))
    generation.outputs.append(output)
    session.add(generation)
    session.commit()
    return output
