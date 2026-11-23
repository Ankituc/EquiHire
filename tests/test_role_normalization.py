import pytest

from backend.main import normalize_role, parse_requirements


@pytest.mark.parametrize(
    ("typed_role", "expected"),
    [
        ("Data ANlsyt", "Data Analyst"),
        ("senor data anlyst", "Data Analyst"),
        ("reporting analist", "Reporting Analyst"),
        ("AI/ML eng", "AI/ML Engineer"),
        ("full stack dev", "Full Stack Developer"),
        ("senior BI analyst", "BI Analyst"),
    ],
)
def test_common_role_aliases_and_typos_normalize(typed_role, expected):
    assert normalize_role(typed_role) == expected


def test_role_alias_uses_the_same_criteria_as_canonical_title():
    assert parse_requirements("", "business intelligence analyst") == parse_requirements("", "Data Analyst")
