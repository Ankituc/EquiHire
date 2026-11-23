"""Evaluate relevance-score regressors on CareerCorpus without saving examples."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from openpyxl import load_workbook
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.linear_model import Ridge
from sklearn.tree import DecisionTreeRegressor

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "public" / "CareerCorpus.xlsx"
DEFAULT_REPORT = ROOT / "reports" / "model_evaluation.json"
STATIC_METRICS = ROOT / "public" / "model_metrics.json"
N_SPLITS = 5
RANDOM_STATE = 42

COLUMN_ALIASES = {
    "id": ("id",),
    "domain": ("domain",),
    "education": ("education",),
    "skills": ("skills and achievements", "skills & achievements"),
    "experience": ("experience",),
    "job_type": ("job_type", "job type"),
    "annotator_1": ("annotator-1", "annotator 1"),
    "annotator_2": ("annotator-2", "annotator 2"),
}


def read_corpus(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError(
            f"CareerCorpus workbook not found: {path}\n"
            "Download the workbook from https://data.mendeley.com/datasets/wzzwn37gmd/1 "
            "and place it at data/public/CareerCorpus.xlsx."
        )

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook.active
    iterator = sheet.iter_rows(values_only=True)
    try:
        header = next(iterator)
    except StopIteration as exc:
        raise ValueError("The CareerCorpus workbook is empty.") from exc

    positions = {str(value).strip().casefold(): index for index, value in enumerate(header) if value is not None}
    columns: dict[str, int] = {}
    for key, aliases in COLUMN_ALIASES.items():
        match = next((positions[alias] for alias in aliases if alias in positions), None)
        if match is None:
            raise ValueError(f"CareerCorpus workbook is missing the '{key}' column.")
        columns[key] = match

    records: list[dict[str, Any]] = []
    for row_index, values in enumerate(iterator, start=2):
        def value(key: str) -> str:
            index = columns[key]
            raw = values[index] if index < len(values) else None
            return "" if raw is None else str(raw).strip()

        domain = value("domain")
        score_a, score_b = value("annotator_1"), value("annotator_2")
        if not domain and not score_a and not score_b:
            continue  # Workbook contains blank formatting rows.
        try:
            scores = float(score_a), float(score_b)
        except ValueError as exc:
            raise ValueError(f"Row {row_index} has a missing or invalid expert score.") from exc
        if any(not 0 <= score <= 1 for score in scores):
            raise ValueError(f"Row {row_index} has an expert score outside the documented 0–1 range.")
        if not domain:
            raise ValueError(f"Row {row_index} has expert scores but no role category.")

        domain = " ".join(domain.split()).title()
        fields = {
            "Role category": domain,
            "Experience level": value("job_type"),
            "Education": value("education"),
            "Skills and achievements": value("skills"),
            "Experience": value("experience"),
        }
        text = " ".join(f"{label}: {content}" for label, content in fields.items() if content)
        if not text:
            raise ValueError(f"Row {row_index} has no text features to model.")
        document_id = value("id") or f"missing-id-row-{row_index}"
        records.append({
            "document_group_id": document_id,
            "domain": domain,
            "text": text,
            "annotator_1": scores[0],
            "annotator_2": scores[1],
            "target": float(np.mean(scores)),
        })
    workbook.close()

    if len(records) < N_SPLITS:
        raise ValueError(f"Need at least {N_SPLITS} usable resume rows for {N_SPLITS}-fold evaluation; found {len(records)}.")
    if len({record["document_group_id"] for record in records}) < N_SPLITS:
        raise ValueError("Need at least five distinct resume IDs for grouped cross-validation.")
    return records


def make_pipeline(regressor: Any) -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, max_features=30_000)),
        ("regressor", regressor),
    ])


def grouped_bootstrap_mae_ci(
    targets: np.ndarray,
    predictions: np.ndarray,
    groups: np.ndarray,
    *,
    iterations: int = 1000,
    seed: int = RANDOM_STATE,
) -> list[float]:
    """Cluster-bootstrap MAE intervals so repeated resume rows stay together."""
    unique_groups = np.unique(groups)
    rows_by_group = {group: np.flatnonzero(groups == group) for group in unique_groups}
    rng = np.random.default_rng(seed)
    estimates = np.empty(iterations, dtype=float)
    for iteration in range(iterations):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        sample_rows = np.concatenate([rows_by_group[group] for group in sampled_groups])
        estimates[iteration] = mean_absolute_error(targets[sample_rows], predictions[sample_rows])
    lower, upper = np.percentile(estimates, [2.5, 97.5])
    return [round(float(lower), 4), round(float(upper), 4)]


def fold_summary(targets: np.ndarray, predictions: np.ndarray) -> dict[str, float]:
    return {
        "mae": round(float(mean_absolute_error(targets, predictions)), 4),
        "rmse": round(float(mean_squared_error(targets, predictions) ** 0.5), 4),
        "r2": round(float(r2_score(targets, predictions)), 4),
    }


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    texts = [record["text"] for record in records]
    targets = np.asarray([record["target"] for record in records], dtype=float)
    groups = np.asarray([record["document_group_id"] for record in records])
    domains = [record["domain"] for record in records]
    splitter = GroupKFold(n_splits=N_SPLITS)
    models = {
        "decision_tree": lambda: make_pipeline(DecisionTreeRegressor(
            max_depth=8, min_samples_leaf=4, random_state=RANDOM_STATE,
        )),
        "knn": lambda: make_pipeline(KNeighborsRegressor(
            n_neighbors=5, weights="distance", metric="cosine", algorithm="brute",
        )),
        "ridge": lambda: make_pipeline(Ridge(alpha=2.0)),
    }

    baseline_predictions = np.zeros(len(records), dtype=float)
    baseline_folds = []
    for train, test in splitter.split(texts, targets, groups):
        baseline_predictions[test] = float(targets[train].mean())
        baseline_folds.append(fold_summary(targets[test], baseline_predictions[test]))

    report: dict[str, Any] = {
        "task": "predict mean expert-assessed resume-to-role relevance score",
        "score_range": [0, 1],
        "rows": len(records),
        "unique_resume_groups": len(set(groups)),
        "domains": dict(Counter(domains)),
        "evaluation": f"{N_SPLITS}-fold GroupKFold cross-validation; repeated resume IDs remain in one fold",
        "target": "mean of Annotator-1 and Annotator-2 scores",
        "uncertainty_method": "95% cluster-bootstrap interval over out-of-fold absolute errors, resampling resume IDs",
        "annotator_agreement": {
            "mae": round(float(mean_absolute_error(
                [record["annotator_1"] for record in records],
                [record["annotator_2"] for record in records],
            )), 4),
            "pearson_correlation": round(float(np.corrcoef(
                [record["annotator_1"] for record in records],
                [record["annotator_2"] for record in records],
            )[0, 1]), 4),
        },
        "models": {},
        "limitations": (
            "Predicts expert-assessed broad role-category relevance, not hiring outcomes or skill proficiency. "
            "Only six categories and 302 professionally crafted/anonymized examples are represented; "
            "performance may not generalize to arbitrary roles or real-world applicant resumes. "
            "Confidence intervals describe resampling variability in this dataset, not deployment guarantees."
        ),
    }
    report["models"]["mean_baseline"] = {
        **fold_summary(targets, baseline_predictions),
        "mae_ci_95": grouped_bootstrap_mae_ci(targets, baseline_predictions, groups),
        "fold_metrics": baseline_folds,
    }

    for name, factory in models.items():
        predictions = np.zeros(len(records), dtype=float)
        fold_metrics = []
        for train, test in splitter.split(texts, targets, groups):
            model = factory()
            model.fit([texts[index] for index in train], targets[train])
            fold_predictions = model.predict([texts[index] for index in test])
            predictions[test] = fold_predictions
            fold_metrics.append(fold_summary(targets[test], fold_predictions))

        by_domain: dict[str, Any] = {}
        for domain in sorted(set(domains)):
            indices = [index for index, item in enumerate(domains) if item == domain]
            by_domain[domain] = {
                "rows": len(indices),
                "mae": round(float(mean_absolute_error(targets[indices], predictions[indices])), 4),
            }
        report["models"][name] = {
            **fold_summary(targets, predictions),
            "mae_ci_95": grouped_bootstrap_mae_ci(targets, predictions, groups),
            "fold_metrics": fold_metrics,
            "mae_by_domain": by_domain,
        }
    return report

def main() -> None:
    records = read_corpus(DEFAULT_DATASET)
    report = evaluate(records)
    DEFAULT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    STATIC_METRICS.parent.mkdir(parents=True, exist_ok=True)
    STATIC_METRICS.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"CareerCorpus rows: {report['rows']} across {report['unique_resume_groups']} resume groups")
    for name, metrics in report["models"].items():
        print(f"{name}: MAE={metrics['mae']:.3f}, RMSE={metrics['rmse']:.3f}, R²={metrics['r2']:.3f}")
    print(f"Annotator disagreement: MAE={report['annotator_agreement']['mae']:.3f}")
    print(f"Aggregate report: {DEFAULT_REPORT}")
    print(f"Dashboard metrics: {STATIC_METRICS}")
    print("These scores estimate agreement with expert ratings and are not hiring predictions.")
    print("MAE intervals use group bootstrap resampling by resume ID; they are not deployment guarantees.")


if __name__ == "__main__":
    main()
