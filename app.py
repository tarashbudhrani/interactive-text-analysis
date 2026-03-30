from io import StringIO

import streamlit as st
import pandas as pd
import plotly.express as px
from text_cleaner import clean_text, clean_text_spacy
from nlp_functions import show_wordcloud , plot_top_ngrams_bar_chart,detect_emotions,detect_overall_sentiment_avg,classify_custom,summarize_large_text
st.set_page_config(page_title="Interactive Text Analysis Platform", layout="wide")


def run_step(title, spinner_message, callback):
    st.subheader(title)
    try:
        with st.spinner(spinner_message):
            return callback()
    except Exception as exc:
        st.error(f"{title} failed: {exc}")
        return None


def render_wordcloud(tokens):
    st.subheader("Word Cloud")
    if not tokens:
        st.info("No meaningful tokens were available for the word cloud.")
        return

    wc_plot = show_wordcloud(tokens)
    if isinstance(wc_plot, str):
        st.error(wc_plot)
        return
    st.pyplot(wc_plot)


def render_emotions(text):
    top_emotions_df = detect_emotions(text)
    if top_emotions_df.empty:
        st.info("No emotion scores were available for this input.")
        return

    max_index = top_emotions_df["Score"].idxmax()
    emotion = top_emotions_df.loc[max_index, "Emotion"]
    score = top_emotions_df.loc[max_index, "Score"]
    st.write(f"Predicted emotion: {emotion}, with {score * 100:.2f}% confidence")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("Top 5 emotions")
        st.dataframe(top_emotions_df, use_container_width=True)
    with col2:
        st.markdown("Emotion confidence chart")
        fig = px.bar(top_emotions_df, x="Emotion", y="Score", color="Emotion")
        fig.update_layout(template="plotly_white", height=290)
        st.plotly_chart(fig, use_container_width=True)


def render_sentiment(text):
    result = detect_overall_sentiment_avg(text)
    if "error" in result:
        st.error(result["error"])
        return

    st.write("Overall sentiment:", result["overall_sentiment"])
    st.dataframe(
        pd.DataFrame(list(result["average_scores"].items()), columns=["Emotion", "Score"]),
        use_container_width=True,
    )


def render_classification(text, csv_mode=False):
    output = classify_custom(text)
    col1, col2 = st.columns(2)

    with col1:
        if csv_mode:
            st.markdown(
                f"Predicted: **{output['predicted_category']}** (Score: {output['score']:.2f})"
            )
            st.write("Top categories:")
            rows = output["all_categories"][:5]
        else:
            st.markdown(
                f"Predicted: **{output['predicted_category']}** (Score: {output['score']:.2f})"
            )
            st.write("Other top predicted categories:")
            rows = output["all_categories"][1:6]

        for label, score in rows:
            st.write(f"{label}: {score:.2f}")

    with col2:
        labels = [label for label, _ in rows]
        scores = [score for _, score in rows]
        fig = px.bar(
            x=labels,
            y=scores,
            color=labels,
            title="Top classification results",
            height=400,
        )
        st.plotly_chart(fig, use_container_width=True)


def render_summary(text):
    summary = summarize_large_text(text)
    st.write(summary)


def render_analysis(text, gram_n, csv_mode=False):
    cleaned = run_step(
        "Text Cleaning",
        "Cleaning and preparing text...",
        lambda: clean_text(text),
    )
    if cleaned is None:
        return

    tokens = run_step(
        "Tokenization",
        "Loading spaCy and extracting tokens...",
        lambda: clean_text_spacy(cleaned),
    )
    if tokens is None:
        return

    if csv_mode:
        st.subheader("Cleaned and Lemmatized Text")
        st.write(" ".join(tokens) if tokens else "No meaningful tokens extracted.")

    render_wordcloud(tokens)
    st.divider()

    st.subheader("N-Gram Analysis")
    plot_top_ngrams_bar_chart(tokens, gram_n=gram_n)
    st.divider()

    run_step(
        "Emotion Detection",
        "Loading the emotion model and analyzing text. The first run may take a minute...",
        lambda: render_emotions(text),
    )
    st.divider()

    run_step(
        "Sentiment Detection",
        "Loading the sentiment model and scoring the text...",
        lambda: render_sentiment(text),
    )
    st.divider()

    run_step(
        "Tone Of Speech Classification",
        "Loading the classification model and ranking tone categories...",
        lambda: render_classification(text, csv_mode=csv_mode),
    )
    st.divider()

    run_step(
        "Summary Generation",
        "Generating a summary. This is usually the slowest step on first run...",
        lambda: render_summary(text),
    )


st.title("INTERACTIVE TEXT ANALYSIS PLATFORM")
st.caption("Hosted-demo friendly setup: the first model-backed request can take longer while NLP models warm up.")
st.divider()

a = st.sidebar.radio("SELECT ONE:", ["Process Textual data", "Process Csv file"])
st.sidebar.info(
    "Tip: on a fresh deploy or restart, the first emotion/sentiment/classification/summary run may take longer."
)

if a == "Process Textual data":
    st.header("Input your textual data.")
    text = st.text_area("Enter your text", height=150)

    if st.button("Analyze"):
        if not text.strip():
            st.warning("Please enter your text.")
        else:
            render_analysis(text, gram_n=2)

if a == "Process Csv file":
    st.header("Upload your CSV file.")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

    if uploaded_file is not None:
        try:
            df = pd.read_csv(StringIO(uploaded_file.getvalue().decode("utf-8")))
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            try:
                df = pd.read_csv(uploaded_file)
            except Exception as exc:
                st.error(f"Could not read this CSV file: {exc}")
                st.stop()
        except Exception as exc:
            st.error(f"Could not read this CSV file: {exc}")
            st.stop()

        if df.empty:
            st.warning("The uploaded CSV is empty.")
            st.stop()

        st.success("File uploaded successfully.")
        st.divider()

        st.header("Choose filtering option.")
        column_name = st.selectbox(
            "Select a column to filter the table",
            df.columns,
        )

        unique_vals = df[column_name].dropna().unique()
        if len(unique_vals) == 0:
            st.warning("The selected filter column has no non-empty values.")
            st.stop()

        selected_value = st.multiselect(
            f"Choose value(s) from {column_name}",
            unique_vals,
        )
        text_processing_column = st.selectbox("Select the text-analysis column", df.columns)

        if selected_value:
            filtered_df = df[df[column_name].isin(selected_value)]
            filtered_text_series = filtered_df[text_processing_column].dropna().astype(str)

            st.subheader("Filtered Data")
            st.dataframe(filtered_df[[column_name, text_processing_column]], use_container_width=True)
            st.divider()

            if filtered_text_series.empty:
                st.warning("The filtered rows do not contain usable text in the selected text column.")
            else:
                text = " ".join(filtered_text_series)
                render_analysis(text, gram_n=3, csv_mode=True)
        else:
            st.info("Choose at least one filter value to analyze the CSV text.")







