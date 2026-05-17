"""Build a downloadable PDF report from TextLens analysis results."""

import io
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
from fpdf import FPDF
from wordcloud import WordCloud


def _safe_text(text):
    if text is None:
        return ""
    return str(text).encode("latin-1", "replace").decode("latin-1")


def wordcloud_png(tokens):
    if not tokens:
        return None
    wc = WordCloud(width=900, height=450, background_color="white").generate(" ".join(tokens))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc)
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    return buf.getvalue()


def plotly_png(fig, width=900, height=480):
    if fig is None:
        return None
    try:
        return fig.to_image(format="png", width=width, height=height, engine="kaleido")
    except Exception:
        return None


def _add_section_title(pdf, title):
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(40, 40, 40)
    pdf.ln(4)
    pdf.cell(0, 8, _safe_text(title), ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)


def _add_paragraph(pdf, text, max_len=2000):
    content = _safe_text(text[:max_len] if len(text) > max_len else text)
    pdf.multi_cell(pdf.epw, 6, content)


def _add_image(pdf, png_bytes, title=None):
    if not png_bytes:
        return
    if title:
        _add_section_title(pdf, title)
    try:
        pdf.image(io.BytesIO(png_bytes), w=190)
    except Exception:
        pdf.cell(0, 6, "(Chart could not be embedded)", ln=True)
    pdf.ln(4)


def _dataframe_lines(df, limit=10):
    lines = []
    for _, row in df.head(limit).iterrows():
        lines.append("  · " + " — ".join(f"{col}: {row[col]}" for col in df.columns))
    return "\n".join(lines)


def build_pdf_report(report):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, _safe_text(report.get("app_name", "TextLens") + " — Analysis Report"), ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(
        0,
        6,
        _safe_text(f"Generated: {report.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M'))}  |  Mode: {report.get('mode', 'text')}"),
        ln=True,
    )
    pdf.ln(6)

    _add_section_title(pdf, "Input (excerpt)")
    _add_paragraph(pdf, report.get("input_excerpt", ""), max_len=2000)

    if report.get("cleaned_text"):
        _add_section_title(pdf, "Cleaned text (excerpt)")
        _add_paragraph(pdf, report["cleaned_text"], max_len=1500)

    images = report.get("images", {})
    _add_image(pdf, images.get("wordcloud"), "Word cloud")
    _add_image(pdf, images.get("ngram"), "N-gram analysis")
    _add_image(pdf, images.get("emotion"), "Emotion detection")

    _add_section_title(pdf, "Emotion results")
    primary = report.get("primary_emotion", "N/A")
    conf = report.get("emotion_confidence")
    conf_txt = f"{conf * 100:.1f}%" if conf is not None else "N/A"
    _add_paragraph(pdf, f"Primary emotion: {primary} ({conf_txt} confidence)")
    emotions_df = report.get("emotions_df")
    if emotions_df is not None and not emotions_df.empty:
        _add_paragraph(pdf, _dataframe_lines(emotions_df))

    _add_section_title(pdf, "Sentiment detection")
    sentiment = report.get("sentiment")
    if isinstance(sentiment, dict) and "error" in sentiment:
        _add_paragraph(pdf, f"Error: {sentiment['error']}")
    elif isinstance(sentiment, dict):
        _add_paragraph(pdf, f"Overall sentiment: {sentiment.get('overall_sentiment', 'N/A')}")
        scores = sentiment.get("average_scores", {})
        for label, score in scores.items():
            _add_paragraph(pdf, f"  · {label}: {score:.4f}")
    else:
        _add_paragraph(pdf, "No sentiment data.")

    _add_image(pdf, images.get("tone"), "Tone of speech")

    _add_section_title(pdf, "Tone of speech")
    tone = report.get("tone") or {}
    _add_paragraph(
        pdf,
        f"Predicted: {tone.get('predicted_category', 'N/A')} (score {tone.get('score', 0):.2f})",
    )
    for label, score in tone.get("top_categories", []):
        _add_paragraph(pdf, f"  · {label}: {score:.2f}")

    summary = report.get("summary")
    if summary:
        _add_section_title(pdf, "Summary")
        _add_paragraph(pdf, summary, max_len=3000)

    out = pdf.output()
    if isinstance(out, bytearray):
        return bytes(out)
    if isinstance(out, bytes):
        return out
    return out.encode("latin-1")
