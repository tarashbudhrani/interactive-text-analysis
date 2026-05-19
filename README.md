# 🔍 TextLens
### *AI-powered text intelligence — emotion, sentiment, tone & summaries*
> Paste any text or upload a CSV → get emotion scores, sentiment breakdown, tone classification, word clouds, n-gram charts, and a downloadable PDF report — all in one click.

---

## ✨ What it does

| Feature | Model / Tool | Output |
|---|---|---|
| 🌥️ **Word Cloud** | spaCy + WordCloud | Visual frequency map of key terms |
| 📊 **N-gram Analysis** | NLTK + Plotly | Top bigrams / trigrams bar chart |
| 💬 **Emotion Detection** | `j-hartmann/distilroberta` | Joy, anger, fear, sadness… (7 classes) |
| 📈 **Sentiment Analysis** | `cardiffnlp/twitter-roberta` | Positive / Neutral / Negative with scores |
| 🎙️ **Tone Classification** | `facebook/bart-large-mnli` | Opinion, factual, story, command… (15 labels) |
| 📝 **Text Summarization** | `facebook/bart-large-cnn` | Abstractive summary (hierarchical chunking) |
| 📄 **PDF Export** | fpdf2 + kaleido | Full report with all charts embedded |

---

## How It Works

Pastes raw text into the TextLens app and clicks "Analyze text" to trigger the full NLP pipeline
<img width="1512" height="663" alt="image" src="https://github.com/user-attachments/assets/52f12532-2da0-4785-9493-e5fec8c23238" />


---

## 🚀 Run locally

```bash
git clone https://github.com/tarashbudhrani/interactive-text-analysis
cd interactive-text-analysis

python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

streamlit run app.py
```

---

## 🧱 Architecture

```
Raw Text / CSV
     │
     ▼
text_cleaner.py        ← regex cleaning + spaCy lemmatization
     │
     ├──▶ WordCloud + N-gram charts     (nltk, wordcloud, plotly)
     │
     ├──▶ split_into_chunks_spacy()     ← handles transformer token limits
     │         │
     │         ├──▶ Emotion Model       (distilroberta, 7 classes)
     │         ├──▶ Sentiment Model     (twitter-roberta, 3 classes)
     │         └──▶ Summarizer          (bart-large-cnn, abstractive)
     │
     ├──▶ Tone Classifier               (bart-large-mnli, zero-shot, 15 labels)
     │
     └──▶ pdf_report.py                 ← fpdf2 + kaleido → downloadable PDF
```

---

## 🗂️ Project Structure

```
├── app.py              # Streamlit UI + orchestration
├── text_cleaner.py     # Regex pipeline + spaCy tokenizer
├── nlp_functions.py    # All 4 Hugging Face models + visualizations
├── pdf_report.py       # PDF report builder
├── requirements.txt
└── runtime.txt         # Python 3.11
```

---

## 🔬 Models used

| Model | Why this one |
|---|---|
| `j-hartmann/emotion-english-distilroberta-base` | Lightweight, multi-label emotion (not just pos/neg) |
| `cardiffnlp/twitter-roberta-base-sentiment` | Trained on 58M tweets — handles informal language well |
| `facebook/bart-large-mnli` | Zero-shot — no labeled "tone" dataset needed |
| `facebook/bart-large-cnn` | Best open-source abstractive summarizer |

---

## 💡 Two modes

- **Text mode** — paste any text, get full analysis + summary + PDF
- **CSV mode** — upload a dataset, filter by column values, analyze aggregated text (e.g. product reviews by category)

---

*Built with Streamlit · spaCy · Hugging Face Transformers · Plotly · fpdf2*
