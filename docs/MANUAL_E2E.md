# Manual upload-to-results check

Use a synthetic or consented sample resume. Do not upload another person's private resume without permission. This check covers the browser UI and local API together.

## Start the application

From the project root, start the API in one terminal:

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Start the UI in another terminal:

```bash
npm run dev
```

Open <http://localhost:5173/> and confirm the header reports **API ready**.

## Check the upload flow

1. Click **Click to upload resume** and choose a small PDF or DOCX with sample skills such as Python, SQL, and Power BI.
2. Enter `Data ANlsyt` as the target role and add `SQL, Python, Power BI` as requirements.
3. Click **Review resume**. Confirm the role normalizes to Data Analyst and the results show extracted skills, requirement coverage, and charts.
4. Confirm matching skills are highlighted and no resume excerpt is displayed in the results table.
5. Change the role or requirements. Confirm the old result clears and the page asks you to review again.
6. Click **Clear results**. Confirm the selected file and result are removed from the current session.
7. Try a non-PDF/DOCX file or an oversized file and confirm the UI gives a readable validation message.

## Expected privacy behavior

The selected file is sent to the local API for in-memory processing. EquiHire has no upload database or persistent resume directory. Clearing the session removes the browser-held file and result state. This local prototype does not make a hiring decision.


## Try the synthetic sample

1. Choose **Try synthetic demo** from the empty state or **explore a synthetic sample** in the hero.
2. Confirm the profile is labeled synthetic and contains the fictional Jordan Lee example.
3. Review the career direction cards at the bottom. They show overlapping skills and possible skills to learn; the overlap is not a probability or proficiency score.
4. Toggle a detected skill off and on. Confirm the career cards update their confirmed skill signals and overlap estimate.
5. Click **Clear results** and confirm the sample is removed from the current page state.

A matching sample job description is in `docs/demo/data-analyst-role.txt`. The UI sample endpoint is generated in memory and uses no real resume or stored file.

## Review evidence quality and privacy

- For each detected skill, inspect its source page or DOCX section label. The app deliberately does not display resume excerpts.
- Toggle off a false skill detection before using career suggestions. The toggle affects suggestion inputs in this session only; it does not alter the uploaded document or claim the skill is absent.
- A source label identifies where a keyword was found, not whether the resume demonstrates competence.
- The selected file stays in browser memory until removed/cleared or the page session ends. The API processes request bytes in memory and does not write uploaded content to disk. The browser's temporary object URL used for PDF preview is revoked when the selected file changes or the component unmounts.
