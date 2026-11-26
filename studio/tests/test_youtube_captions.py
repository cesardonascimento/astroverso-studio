from app.lib.youtube import ParseJson3


def test_word_offsets_become_timed_words():
    data = {"events": [{"tStartMs": 1000, "dDurationMs": 2000,
                        "segs": [{"utf8": "ola"}, {"utf8": " mundo", "tOffsetMs": 400}, {"utf8": " >>", "tOffsetMs": 800}]}]}
    words = ParseJson3().execute(data)
    assert [(w.text, w.start, w.end) for w in words] == [("ola", 1.0, 1.4), ("mundo", 1.4, 1.9)]


def test_phrase_time_is_spread_by_word_length():
    data = {"events": [{"tStartMs": 0, "dDurationMs": 1000, "segs": [{"utf8": "a bbb"}]},
                       {"tStartMs": 2000, "dDurationMs": 500, "segs": [{"utf8": "[Música]"}]}]}
    words = ParseJson3().execute(data)
    assert [w.text for w in words] == ["a", "bbb"]
    assert words[0].end == words[1].start == 0.333
