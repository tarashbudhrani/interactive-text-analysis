# TextLens

AI-powered text analysis: emotion, sentiment, tone, word clouds, n-grams, summaries, and PDF reports.

**Live app:** [https://textlens.streamlit.app](https://textlens.streamlit.app) *(after Streamlit Cloud deploy)*

## Run locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. Open [share.streamlit.io](https://share.streamlit.io).
3. **New app** → repo `tarashbudhrani/interactive-text-analysis` → branch `main` → main file `app.py`.
