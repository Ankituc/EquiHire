# CareerCorpus model guide

## Dataset and target

EquiHire uses **CareerCorpus**, a public dataset of 302 de-identified resume examples across six domains: Teacher, Finance, Apparel, Accountant, Banking, and Research Assistant. Each resume includes two expert-assigned relevance scores from 0 to 1 for its occupational category. This project uses their mean as a continuous target and compares regressors that estimate that expert relevance score from the resume text and category.

This target is an expert rating of broad resume-to-category relevance. It is not a hiring outcome, a validated measure of skill proficiency, or evidence that a candidate should be hired. The category set is small and limited; results should not be generalized to arbitrary job titles.

## Attribution and local data

CareerCorpus is released under **CC BY 4.0**. The dataset page reports that names, contact details, addresses, and other identifying information were removed. It includes examples sourced from professionally crafted LiveCareer resumes and public LinkedIn profiles. Treat the data as sensitive even after de-identification, do not try to re-identify anyone, and do not commit the workbook to Git. The uploaded resume feature remains session-only and never adds a user's file to this offline research dataset.

Citation: Adiba, Adiba Fairooz Chowdhury; Chowdhury, Md Sagor; Banu, Ayesha; Hossain, Riad (2025), “CareerCorpus : A Comprehensive Dataset of Annotated Resumes”, Mendeley Data, V1, doi: [10.17632/wzzwn37gmd.1](https://doi.org/10.17632/wzzwn37gmd.1).

## Models and evaluation

`python -m ml.train_evaluate` compares a TF-IDF + Decision Tree regressor, TF-IDF + KNN regressor, and TF-IDF + Ridge regressor with five-fold grouped cross-validation and a mean baseline. It reports MAE, RMSE, R², per-domain MAE, fold-level metrics, and a 95% cluster-bootstrap interval for MAE that resamples whole resume IDs. It also reports the two human annotators' disagreement as context. All rows with the same anonymized resume ID stay in one validation fold and in one bootstrap unit. The report contains aggregate metrics only, not resume text or per-person predictions. The intervals measure resampling variability within this small dataset; they are not deployment guarantees.

The published study reports moderate annotator agreement and warns that the sample is small, English-only, and includes professionally crafted examples. EquiHire's own cross-validation results are a local benchmark; they are not expected to match the paper's results because this project uses different models and a grouped split.

## Re-run

The workbook is kept locally at `data/public/CareerCorpus.xlsx` and ignored by Git. To fetch a fresh copy, use the dataset's [Mendeley Data page](https://data.mendeley.com/datasets/wzzwn37gmd/1). Then install project requirements and run `python -m ml.train_evaluate`. Aggregate output is written to the ignored `reports/model_evaluation.json`.
