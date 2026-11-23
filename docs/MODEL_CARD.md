# EquiHire model card

**Project version:** 0.2.0  
**Model task:** estimate expert-assessed resume-to-broad-role-category relevance.

## Intended use

This is a portfolio and research demonstration for comparing text-based regression approaches. The estimate may be used to inspect aggregate model behavior against the documented CareerCorpus labels. The application requires human review of resume text and role criteria.

## Out of scope

The model is not designed to predict hiring decisions, job offers, job performance, or individual skill proficiency. It must not be used as an automatic screening or rejection system. The score is a dataset-specific relevance estimate, not a probability of success.

## Models and input

The benchmark compares TF-IDF text features with a Decision Tree regressor, K-Nearest Neighbors regressor, and Ridge regression against a mean baseline. The target is the average of two expert relevance ratings. The offline input combines the broad role category with job type, education, skills/achievements, and experience fields.

The benchmark currently contains 302 examples grouped under 301 resume IDs and six categories: Accountant, Apparel, Banking, Finance, Research Assistant, and Teacher. GroupKFold keeps repeated resume IDs together. Reported results include MAE, RMSE, R², per-category MAE, fold metrics, and group-bootstrap MAE intervals.

## Current benchmark snapshot

Values below come from `public/model_metrics.json`; rerunning evaluation may update them.

| Model | MAE | RMSE | R² |
| --- | ---: | ---: | ---: |
| Mean baseline | 0.1380 | 0.1894 | -0.0137 |
| Decision Tree | 0.1034 | 0.1481 | 0.3801 |
| KNN | 0.0833 | 0.1290 | 0.5292 |
| Ridge | 0.1024 | 0.1501 | 0.3629 |

## Limitations and risks

The dataset is small, English-language, professionally crafted/de-identified, and represents only six broad occupations. It does not contain actual hiring outcomes or validated proficiency labels. Performance on technology jobs, other languages, real applicant populations, or future data is unknown. Annotator disagreement is non-zero, and estimates may reflect dataset conventions. The benchmark must not be described as evidence of fairness across demographic groups; the dataset does not provide a validated basis for that claim.

The live resume-review path uses explicit role skill criteria and text-similarity signals for a wider role catalog. The CareerCorpus regressors are only available for the six categories above. These are separate signals and should not be conflated.

## Privacy and human oversight

Uploaded resumes are processed in request memory and browser session state only. They are not saved, used to retrain this model, or added to CareerCorpus. Confirm extracted details and evidence against the original resume. Apply consistent criteria and keep human reviewers responsible for decisions.

## Reproducibility

See [README setup](../README.md#fresh-clone-setup) and the [data card](DATA_CARD.md). The workbook is intentionally excluded from Git; download it from the attributed source and place it at `data/public/CareerCorpus.xlsx` before training or using live regression estimates for supported categories.


## Evaluation interpretation and failure cases

The benchmark scores describe agreement with the dataset's expert relevance labels, not correctness on an individual applicant. A lower MAE is better on this test split, but a modest dataset and six categories do not establish broad generalization. R² may vary substantially by split and can be negative when a model performs worse than predicting the average label.

Expected weak cases include:

- A technical resume compared to a role absent from CareerCorpus: the benchmark regression is unavailable; only the separate curated skill-profile comparison can run.
- A scanned, low-resolution, rotated, or multi-column resume: OCR and reading order can miss or scramble text.
- Synonyms, acronyms, misspellings, emerging tools, and non-English terms outside the curated vocabulary: skill mentions may be missed even when the candidate has the capability.
- A resume that lists a tool without meaningful project evidence: text matching can count the mention but cannot verify practical proficiency.
- A candidate whose experience is described implicitly or across dates: simple year extraction may report "Not detected" or an incomplete duration.

Review extracted skill source labels against the document, correct false detections using the skill toggles, and treat each suggestion as a prompt for exploration. Do not compare candidates using these estimates as a hiring score.
