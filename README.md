# TextLens

AI-powered text analysis: emotion, sentiment, tone, word clouds, n-grams, summaries, and PDF reports.

## Live app (deploy under your GitHub account)

The old URL `interactive-text-analysis.streamlit.app` is **not** linked to `tarashbudhrani@gmail.com` / your current GitHub login. Create a **new** app once:

1. Sign in at **[share.streamlit.io](https://share.streamlit.io)** with **GitHub** (account: `tarashbudhrani`), not email-only.
2. Open this deploy link:  
   **[Deploy TextLens on Streamlit Cloud](https://share.streamlit.io/deploy?repository=tarashbudhrani/interactive-text-analysis&branch=main&mainModule=app.py)**
3. Pick an app URL (e.g. `textlens`) → your live link will be:  
   **`https://textlens.streamlit.app`** (or whatever name you choose)
4. Wait 5–15 minutes for the first build.

If you see “no access”: **Settings → Linked accounts** and connect the same GitHub user that owns the repo.

## Run locally

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Repo

https://github.com/tarashbudhrani/interactive-text-analysis
