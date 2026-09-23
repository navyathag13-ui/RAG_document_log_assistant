from app.services.evaluation_service import score_answer

CHUNKS = [
    {"text": "The main coolant pump must be inspected every 500 operating hours. Replace the shaft seals once a year.", "score": 0.82, "doc_name": "manual.txt"},
]


def test_returns_expected_fields():
    scores = score_answer("How often is the pump inspected?", "Inspect the coolant pump every 500 operating hours.", CHUNKS)
    for key in ("relevance_score", "groundedness_score", "completeness_score", "clarity_score", "overall_score"):
        assert key in scores
        assert 0.0 <= scores[key] <= 1.0


def test_grounded_answer_beats_unrelated_answer():
    good = score_answer("How often is the pump inspected?", "Inspect the coolant pump every 500 operating hours and replace the shaft seals yearly.", CHUNKS)
    bad = score_answer("How often is the pump inspected?", "Astronomers recently discovered several distant galaxies using infrared telescopes.", CHUNKS)
    assert good["groundedness_score"] > bad["groundedness_score"]


def test_admitting_no_information_caps_groundedness():
    scores = score_answer("What is the limit?", "The documents do not contain any information about this pump limit value.", CHUNKS)
    assert scores["groundedness_score"] <= 0.35


def test_no_chunks_means_zero_relevance():
    assert score_answer("Anything?", "Some answer text.", [])["relevance_score"] == 0.0
