import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

from text_cleaner import clean_text, clean_text_spacy
from nlp_functions import (
    show_wordcloud,
    plot_top_ngrams_bar_chart,
    build_ngram_figure,
    detect_emotions,
    detect_overall_sentiment_avg,
    classify_custom,
    summarize_large_text,
)
from pdf_report import build_pdf_report, wordcloud_png, plotly_png

APP_NAME = "TextLens"
APP_TAGLINE = "AI-powered text intelligence for emotion, sentiment, tone & summaries"
SIDEBAR_TAGLINE = "Understand any text in seconds"

st.set_page_config(
    page_title=f"{APP_NAME} · NLP Analytics",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=Instrument+Serif:ital@0;1&display=swap');

        .stApp {
            background: radial-gradient(ellipse 120% 80% at 10% -10%, rgba(99, 102, 241, 0.18), transparent 50%),
                        radial-gradient(ellipse 80% 60% at 90% 0%, rgba(34, 211, 238, 0.12), transparent 45%),
                        linear-gradient(180deg, #0c0c10 0%, #12121a 40%, #0f0f14 100%);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #14141f 0%, #0e0e14 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }

        [data-testid="stSidebar"] .stMarkdown,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stRadio label {
            font-family: 'DM Sans', sans-serif !important;
        }

        .block-container { padding-top: 2rem; max-width: 1100px; }

        h1, h2, h3, .hero-title {
            font-family: 'Instrument Serif', Georgia, serif !important;
            letter-spacing: -0.02em;
        }

        p, .stMarkdown, label, .stTextArea textarea, .stSelectbox label {
            font-family: 'DM Sans', sans-serif !important;
        }

        .hero-wrap { padding: 2rem 0 1.5rem; margin-bottom: 0.5rem; }
        .hero-title {
            font-size: 2.75rem; font-weight: 400; color: #f8fafc;
            margin: 0 0 0.35rem 0; line-height: 1.15;
        }
        .hero-title span {
            background: linear-gradient(135deg, #a5b4fc 0%, #22d3ee 50%, #c4b5fd 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .hero-tagline { color: #94a3b8; font-size: 1.05rem; margin: 0; max-width: 36rem; line-height: 1.6; }

        .sidebar-brand {
            padding: 0.5rem 0 1.25rem;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 1.25rem;
        }
        .sidebar-brand h2 {
            font-family: 'Instrument Serif', Georgia, serif !important;
            font-size: 1.65rem; color: #f1f5f9; margin: 0;
        }
        .sidebar-brand p { color: #64748b; font-size: 0.8rem; margin: 0.25rem 0 0 0; }

        .nav-label {
            color: #64748b; font-size: 0.7rem; font-weight: 600;
            letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.5rem;
        }

        .section-header {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin: 1.75rem 0 1rem 0;
        }
        .section-header h3 {
            color: #e2e8f0 !important; font-size: 1.2rem !important;
            margin: 0 0 0.25rem 0 !important;
            font-family: 'DM Sans', sans-serif !important; font-weight: 600 !important;
        }
        .section-header .section-desc {
            color: #64748b; font-size: 0.85rem; margin: 0; line-height: 1.5;
        }

        .insight-pill {
            display: inline-block;
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(129, 140, 248, 0.35);
            color: #c7d2fe;
            padding: 0.35rem 0.85rem;
            border-radius: 999px;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }

        .stButton > button {
            font-family: 'DM Sans', sans-serif !important;
            font-weight: 600;
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.55rem 1.75rem !important;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
        }

        [data-testid="stFileUploader"] {
            background: rgba(255,255,255,0.02);
            border-radius: 12px;
            padding: 0.5rem;
        }

        .footer-note {
            text-align: center; color: #475569; font-size: 0.8rem;
            padding: 2rem 0 1rem;
            border-top: 1px solid rgba(255,255,255,0.05);
            margin-top: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(subtitle=None):
    sub = subtitle or APP_TAGLINE
    st.markdown(
        f"""
        <div class="hero-wrap">
            <h1 class="hero-title"><span>{APP_NAME}</span></h1>
            <p class="hero-tagline">{sub}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title, description=""):
    desc_html = f'<p class="section-desc">{description}</p>' if description else ""
    st.markdown(
        f'<div class="section-header"><h3>{title}</h3>{desc_html}</div>',
        unsafe_allow_html=True,
    )


def plotly_style(fig, height=None):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color="#94a3b8"),
        margin=dict(l=20, r=20, t=40, b=20),
    )
    if height:
        fig.update_layout(height=height)
    return fig


def show_pdf_download(report):
    try:
        pdf_bytes = build_pdf_report(report)
        filename = f"textlens_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        section_header("Export report", "Save all results, tables, and charts to your computer as a PDF.")
        st.download_button(
            label="Download full report (PDF)",
            data=pdf_bytes,
            file_name=filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Could not build PDF: {e}")


def run_analysis(text, tokens, gram_n, mode_label, include_summary=False):
    """Run full NLP pipeline, display results, and prepare PDF report data."""
    images = {}
    report = {
        "app_name": APP_NAME,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mode": mode_label,
        "input_excerpt": text[:800],
        "cleaned_text": (" ".join(tokens)[:800] if tokens else ""),
        "images": images,
        "summary": None,
    }

    if tokens:
        section_header("Word cloud", "Most frequent terms after cleaning and lemmatization.")
        wc_plot = show_wordcloud(tokens)
        st.pyplot(wc_plot)
        images["wordcloud"] = wordcloud_png(tokens)

    section_header("N-gram analysis", f"Most common {'pairs' if gram_n == 2 else 'triplets'} in your text.")
    ngram_fig = build_ngram_figure(tokens, gram_n=gram_n) if tokens else None
    if ngram_fig is not None:
        styled_ngram = plotly_style(ngram_fig)
        st.plotly_chart(styled_ngram, use_container_width=True)
        images["ngram"] = plotly_png(styled_ngram, height=500)
    else:
        plot_top_ngrams_bar_chart(tokens, gram_n=gram_n)

    section_header("Emotion detection", "Top emotional signals detected by the model.")
    top_emotions_df = detect_emotions(text)
    max_index = top_emotions_df["Score"].idxmax()
    emotion = top_emotions_df.loc[max_index, "Emotion"]
    score = top_emotions_df.loc[max_index, "Score"]
    report["primary_emotion"] = emotion
    report["emotion_confidence"] = score
    report["emotions_df"] = top_emotions_df

    st.markdown(
        f'<span class="insight-pill">Primary emotion: <strong>{emotion}</strong> · {score * 100:.1f}% confidence</span>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Top 5 emotions**")
        st.dataframe(top_emotions_df, use_container_width=True)
    with col2:
        st.markdown("**Confidence chart**")
        emotion_fig = px.bar(top_emotions_df, x="Emotion", y="Score", color="Emotion")
        emotion_fig = plotly_style(emotion_fig, height=290)
        st.plotly_chart(emotion_fig, use_container_width=True)
        images["emotion"] = plotly_png(emotion_fig, height=320)

    section_header("Sentiment detection", "Overall positive, neutral, or negative tone.")
    result = detect_overall_sentiment_avg(text)
    report["sentiment"] = result
    if "error" in result:
        st.write("Error:", result["error"])
    else:
        st.markdown(
            f'<span class="insight-pill">Overall: <strong>{result["overall_sentiment"]}</strong></span>',
            unsafe_allow_html=True,
        )
        st.write(
            "Average scores:",
            pd.DataFrame(
                list(result["average_scores"].items()),
                columns=["Sentiment", "Score"],
            ),
        )

    section_header("Tone of speech", "How the text reads — factual, opinion, question, story, and more.")
    tone_output = classify_custom(text)
    report["tone"] = {
        "predicted_category": tone_output["predicted_category"],
        "score": tone_output["score"],
        "top_categories": tone_output["all_categories"][:5],
    }

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"**Predicted:** {tone_output['predicted_category']} · score {tone_output['score']:.2f}"
        )
        st.write("Other top categories:")
        for label, sc in tone_output["all_categories"][1:6]:
            st.write(f"· {label}: {sc:.2f}")
    with col2:
        labels = [lb for lb, _ in tone_output["all_categories"][1:6]]
        scores = [sc for _, sc in tone_output["all_categories"][1:6]]
        tone_fig = px.bar(x=labels, y=scores, color=labels, title="Top predicted categories")
        tone_fig = plotly_style(tone_fig, height=400)
        st.plotly_chart(tone_fig, use_container_width=True)
        images["tone"] = plotly_png(tone_fig, height=420)

    if include_summary:
        section_header("Summary generation", "A concise summary of your text (best with 40+ words).")
        with st.spinner("Generating summary — first run may take a minute…"):
            summary = summarize_large_text(text)
        report["summary"] = summary
        if summary.startswith("Summary failed:") or summary.startswith("Text is too short"):
            st.warning(summary)
        else:
            st.info(summary)

    show_pdf_download(report)


inject_styles()

with st.sidebar:
    st.markdown(
        f"""
        <div class="sidebar-brand">
            <h2>{APP_NAME}</h2>
            <p>{SIDEBAR_TAGLINE}</p>
        </div>
        <p class="nav-label">Workspace</p>
        """,
        unsafe_allow_html=True,
    )
    a = st.radio(
        "Mode",
        ["Process Textual data", "Process Csv file"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown(
        """
        <p style="color:#64748b; font-size:0.8rem; line-height:1.5;">
        <strong style="color:#94a3b8;">Tip:</strong> For summaries, use at least 40–50 words.
        After analysis, download a PDF with all charts and results.
        </p>
        """,
        unsafe_allow_html=True,
    )

render_hero()

if a == "Process Textual data":
    section_header("Text input", "Paste any paragraph, article, or review to run the full NLP pipeline.")
    text = st.text_area(
        "Enter your text",
        height=180,
        placeholder="Paste your text here — reviews, articles, social posts, survey responses…",
        label_visibility="collapsed",
    )
    if st.button("Analyze text", type="primary", use_container_width=False):
        if not text.strip():
            st.warning("Please enter your text")
        else:
            cleaned = clean_text(text)
            tokens = clean_text_spacy(cleaned)
            run_analysis(text, tokens, gram_n=2, mode_label="Text input", include_summary=True)

elif a == "Process Csv file":
    section_header("Upload dataset", "Import a CSV and analyze text from a selected column.")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv", label_visibility="collapsed")
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        st.success("File uploaded successfully")
        st.divider()

        section_header("Filter & configure", "Narrow rows, then pick the column that contains text.")
        column_name = st.selectbox("Filter by column", df.columns)
        unique_vals = df[column_name].dropna().unique()
        selected_value = st.multiselect(f"Values in “{column_name}”", unique_vals)
        text_processing_column = st.selectbox("Text column for analysis", df.columns)

        if selected_value:
            filtered_df = df[df[column_name].isin(selected_value)]
            filtered_df = filtered_df[text_processing_column]

            section_header("Filtered preview", "Rows included in this analysis run.")
            st.dataframe(filtered_df, use_container_width=True)
            text = " ".join(filtered_df.dropna().astype(str))

            cleaned = clean_text(text)
            tokens = clean_text_spacy(cleaned)

            section_header("Cleaned text", "Normalized tokens after preprocessing.")
            st.write(" ".join(tokens) if tokens else "No meaningful tokens extracted")

            run_analysis(
                text,
                tokens,
                gram_n=3,
                mode_label=f"CSV ({column_name}={', '.join(map(str, selected_value[:3]))})",
                include_summary=False,
            )

st.markdown(
    f"""
    <p class="footer-note">
        {APP_NAME} · Built with Streamlit, spaCy & Hugging Face Transformers
    </p>
    """,
    unsafe_allow_html=True,
)
