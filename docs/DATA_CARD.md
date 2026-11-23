# EquiHire data card: CareerCorpus

## Dataset identity

- **Name:** CareerCorpus: A Comprehensive Dataset of Annotated Resumes
- **Version:** Mendeley Data V1
- **Source:** [Mendeley Data](https://data.mendeley.com/datasets/wzzwn37gmd/1)
- **Citation:** Adiba, Adiba Fairooz Chowdhury; Chowdhury, Md Sagor; Banu, Ayesha; Hossain, Riad (2025), *CareerCorpus: A Comprehensive Dataset of Annotated Resumes*, V1, doi: [10.17632/wzzwn37gmd.1](https://doi.org/10.17632/wzzwn37gmd.1).
- **License:** CC BY 4.0, as stated on the dataset page. Preserve attribution and follow the license when redistributing adapted material.

## Contents and labels

The local workbook contains 302 resume rows and 301 distinct resume IDs across six broad categories: Accountant, Apparel, Banking, Finance, Research Assistant, and Teacher. The modeling workflow reads the resume ID, category, job type, education, skills/achievements, experience, and two expert-assigned relevance ratings. The target used by EquiHire is the mean of the two ratings on a 0–1 scale.

The labels describe expert-assessed broad category relevance. They are not hiring decisions, employment outcomes, or validated skill-proficiency measurements.

## Collection and privacy notes

The dataset source describes examples as professionally crafted and de-identified, with direct identifiers removed. De-identification does not guarantee that examples cannot be sensitive. Do not attempt re-identification, publish raw resume text, or commit the workbook to this repository. Keep it in the Git-ignored `data/public/` directory.

Uploaded user resumes are separate from this research dataset. EquiHire processes upload bytes in API request memory and does not add them to the workbook or save them for model training. The selected file and result remain in browser memory until the user clears the review, removes the file, or ends the page session. No raw resume text or excerpts are returned by the API.

## Known limitations

The sample is small, English-language, and limited to six categories. Resume styles and content may not represent the broader applicant population. Results may not generalize to technical occupations, different regions/languages, or real-world hiring. The two annotators can disagree. The dataset does not support a demographic fairness claim or hiring-outcome prediction.

## Local setup

1. Download the workbook from the source above and review its license and attribution conditions.
2. Place it at `data/public/CareerCorpus.xlsx` in the project root. That path is ignored by Git.
3. Install `requirements.txt` and run `python -m ml.train_evaluate` to regenerate aggregate model metrics.
4. The committed `public/model_metrics.json` supports the dashboard benchmark display without the workbook. Live relevance estimates for the six supported categories require the local workbook; other resume-review functions remain available without it.

The workbook is read with `openpyxl`; Pandas is not required by the current pipeline.
