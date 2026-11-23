"""In-memory inference using the local CareerCorpus research benchmark."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor

from .train_evaluate import make_pipeline, read_corpus
from pathlib import Path

ROLE_DOMAINS = {
    "teacher": "Teacher",
    "finance": "Finance",
    "apparel": "Apparel",
    "accountant": "Accountant",
    "accounting": "Accountant",
    "banking": "Banking",
    "research assistant": "Research Assistant",
}


def match_domain(role: str) -> str | None:
    normalized = " ".join(role.casefold().split())
    if normalized in ROLE_DOMAINS:
        return ROLE_DOMAINS[normalized]
    matches = {domain for alias, domain in ROLE_DOMAINS.items() if alias in normalized}
    return matches.pop() if len(matches) == 1 else None


@lru_cache(maxsize=1)
def _fit_models() -> tuple[dict[str, Pipeline], dict[str, int]]:
    dataset = Path(__file__).resolve().parents[1] / "data" / "public" / "CareerCorpus.xlsx"
    records = read_corpus(dataset)
    texts = [row["text"] for row in records]
    targets = [row["target"] for row in records]
    models = {
        "decision_tree": make_pipeline(DecisionTreeRegressor(max_depth=8, min_samples_leaf=4, random_state=42)),
        "knn": make_pipeline(KNeighborsRegressor(n_neighbors=5, weights="distance", metric="cosine", algorithm="brute")),
        "ridge": make_pipeline(Ridge(alpha=2.0)),
    }
    for model in models.values():
        model.fit(texts, targets)
    return models, {"training_rows": len(records), "training_resume_groups": len({row["document_group_id"] for row in records})}


def predict_role_relevance(role: str, resume_text: str) -> dict[str, Any] | None:
    """Return broad category relevance estimates only for supported corpus roles."""
    domain = match_domain(role)
    if not domain or not resume_text.strip():
        return None
    models, provenance = _fit_models()
    model_text = f"Role category: {domain} Experience level: Education: Skills and achievements: Experience: {resume_text}"
    estimates = {
        name: round(min(1.0, max(0.0, float(model.predict([model_text])[0]))), 3)
        for name, model in models.items()
    }
    return {
        "domain": domain,
        "score_range": [0, 1],
        "estimates": estimates,
        "source": "CareerCorpus expert relevance annotations",
        **provenance,
    }
