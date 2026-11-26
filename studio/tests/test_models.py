from app.models import Event, Generation, Job, Output, OutputVersion, VersionKind


def test_generation_keeps_outputs_versions_and_events(session):
    generation = Generation(instance="a", algorithm="corte", inputs={"url": "x"})
    output = Output(network="tiktok", strategy="auto")
    output.versions.append(OutputVersion(version=1, kind=VersionKind.INITIAL, plan={"title": "t"},
                                         strategy_name="viral"))
    generation.outputs.append(output)
    session.add(generation)
    session.flush()
    session.add(Event(generation_id=generation.id, step="download", message="ok"))
    session.add(Job(instance="a", generation_id=generation.id, step="download"))
    session.commit()

    loaded = session.get(Generation, generation.id)
    assert loaded.outputs[0].versions[0].plan == {"title": "t"}
    assert loaded.events[0].step == "download"
    assert loaded.state == "PREPARING"
