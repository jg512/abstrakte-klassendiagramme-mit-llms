from benchmarks.java_literal.run import run_cases


def test_all_modern_literal_cases_match_exactly():
    result = run_cases()
    assert result["cases"] == 20
    assert result["failed"] == 0, [
        item for item in result["results"] if not item["ok"]
    ]
