# Interactive Text Analysis Platform

This project is a Streamlit app for interactive NLP analysis on freeform text and CSV uploads. It includes:

- text cleaning and lemmatization
- word cloud generation
- n-gram analysis
- emotion detection
- sentiment detection
- tone/speech classification
- summary generation

## Local setup

Use Python 3.12 to match the tested deployment/runtime target.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py
```

If you are not inside the virtual environment, you can also run:

```bash
.venv/bin/streamlit run app.py
```

## Render deployment

This repo includes `render.yaml` and `runtime.txt` for a Render web service deployment.

### Recommended steps

1. Push this project to a private GitHub repository.
2. In Render, create a new Blueprint or Web Service from that repo.
3. Confirm the build command:

```bash
pip install -r requirements.txt && python -m spacy download en_core_web_sm
```

4. Confirm the start command:

```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```

5. Use at least the `Starter` plan for a more reliable demo because the app downloads and runs multiple transformer models.

## Cold starts and resource notes

- The first request after deploy or restart can be slow because Hugging Face models may need to download and initialize.
- The app is configured to use CPU-safe defaults so it works in hosted Linux environments without Apple `mps`.
- Matplotlib and Hugging Face caches are redirected to writable temporary directories.
- Summary generation is the slowest feature and may take noticeably longer than the other analyses.

## Smoke-test checklist

- Enter sample text and verify word cloud, n-grams, emotion, sentiment, tone, and summary outputs.
- Upload a CSV with a text column and a filterable column.
- Test a filtered result with real text, nulls, and an empty selection.
- Confirm the app shows progress/loading messages during first-run model warm-up.
