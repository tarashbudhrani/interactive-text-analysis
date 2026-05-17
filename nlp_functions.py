# WORD CLOUD
from wordcloud import WordCloud
import matplotlib.pyplot as plt
import streamlit as st
# WORD CLOUD
def show_wordcloud(text):
    try:
        wordcloud= WordCloud(width=800, height=400, background_color="white").generate(" ".join(text))
        # for wordcloud we pass text not tokens
        plt.figure(figsize=(10,5))
        plt.imshow(wordcloud)
        plt.axis("off")
        return plt
    except Exception as e:
        return f"Error generating word cloud:m {e}"


# N-GRAM ANALYSIS
from nltk.util import ngrams
from collections import Counter
import plotly.graph_objects as go

def build_ngram_figure(tokens, gram_n=3, top_n=15):
    ngram = list(ngrams(tokens, gram_n))
    ngram_counts = Counter(ngram).most_common(top_n)
    if not ngram_counts:
        return None

    labels = []
    counts = []
    for gram, count in ngram_counts:
        labels.append(" ".join(gram))
        counts.append(count)

    gram_label = "Bigrams" if gram_n == 2 else "Trigrams" if gram_n == 3 else f"{gram_n}-grams"
    fig = go.Figure(
        data=[go.Bar(x=labels, y=counts, text=counts, textposition="outside")]
    )
    fig.update_layout(
        height=550,
        title=f"Top {top_n} {gram_label}",
        xaxis_title="N-gram",
        yaxis_title="Frequency",
    )
    return fig


def plot_top_ngrams_bar_chart(tokens, gram_n=3, top_n=15):
    try:
        fig = build_ngram_figure(tokens, gram_n=gram_n, top_n=top_n)
        if fig is None:
            raise ValueError("No n-grams found in the given token list")
        st.plotly_chart(fig)
    except Exception as e:
        print(f"An Error Occured: {e}")


#CREATING CHUNKS
import spacy

_nlp = None


def _get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def split_into_chunks_spacy(text, max_length=500):
    nlp = _get_nlp()
    doc = nlp(text)
    chunks = []
    current_chunk = ""

    for sent in doc.sents:
        sentence = sent.text.strip()
        if len(current_chunk) + len(sentence) <= 500:
            current_chunk += " " + sentence
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks



#EMOTIONAL ANALYSIS
from transformers import pipeline
import pandas as pd
from collections import defaultdict

_emotion_classifier = None
_sentiment_classifier = None
_tone_classifier = None


def _get_emotion_classifier():
    global _emotion_classifier
    if _emotion_classifier is None:
        model_name = "j-hartmann/emotion-english-distilroberta-base"
        _emotion_classifier = pipeline(
            "text-classification",
            model=model_name,
            tokenizer=model_name,
            top_k=None,
        )
    return _emotion_classifier


def detect_emotions(text):
    chunks = split_into_chunks_spacy(text)
    emotion_totals = {}
    emotion_count = defaultdict(int)
    emotion_classifier = _get_emotion_classifier()

    for chunk in chunks:
        results = emotion_classifier(chunk)[0]
        for result in results:
            label = result["label"]
            score = result["score"]
            emotion_totals[label] = emotion_totals.get(label, 0) + score
            emotion_count[label] += 1

    emotion_counts = dict(emotion_count)

    emotion_averages = {label: emotion_totals[label] / emotion_counts[label] for label in emotion_totals}
    sorted_emotions = sorted(emotion_averages.items(), key=lambda x: x[1], reverse=True)
    top_5 = sorted_emotions[:5]
    df = pd.DataFrame(top_5, columns=["Emotion", "Score"])
    return df

# SENTIMENT ANALYSIS


def _get_sentiment_classifier():
    global _sentiment_classifier
    if _sentiment_classifier is None:
        model_name = "cardiffnlp/twitter-roberta-base-sentiment"
        _sentiment_classifier = pipeline(
            "sentiment-analysis",
            model=model_name,
            tokenizer=model_name,
            top_k=None,
        )
    return _sentiment_classifier


def detect_overall_sentiment_avg(text):
    try:
        sentiment_labels = {
            "LABEL_0": "Negative",
            "LABEL_1": "Neutral",
            "LABEL_2": "Positive"
        }
        chunks = split_into_chunks_spacy(text)
        if not chunks:
            return {"error": "No text to analyze after splitting."}

        score_total = {"Negative": 0.0, "Neutral": 0.0, "Positive": 0.0}
        chunk_count = len(chunks)
        sentiment_classifier = _get_sentiment_classifier()

        for chunk in chunks:
            outputs = sentiment_classifier(chunk)
            results = outputs[0] if outputs else []
            for res in results:
                label = sentiment_labels[res["label"]]
                score_total[label] += res["score"]

        avg_score = {}
        for label in score_total:
            avg_score[label] = score_total[label] / chunk_count
        overall_sentiment = max(avg_score, key=avg_score.get)
        return {
            "overall_sentiment": overall_sentiment,
            "average_scores": avg_score
        }

    except Exception as e:
        return {"error": str(e)}


#TONE OF SPEECH CLASSIFICATION

labels = [
    "factual",
    "opinion",
    "question",
    "command",
    "emotion",
    "personal experience",
    "suggestion",
    "story",
    "prediction",
    "warning",
    "instruction",
    "definition",
    "narrative",
    "news",
    "argument"
]


def _get_tone_classifier():
    global _tone_classifier
    if _tone_classifier is None:
        _tone_classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
        )
    return _tone_classifier


def classify_custom(text):
    result = _get_tone_classifier()(text, candidate_labels=labels)
    return {
        "text": text,
        "predicted_category": result["labels"][0],
        "score": result["scores"][0],
        "all_categories": list(zip(result["labels"], result["scores"]))
    }



# TEXT SUMMARIZATION (Transformers v5 removed the "summarization" pipeline)
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

_SUMMARY_MODEL_NAME = "facebook/bart-large-cnn"
_summary_tokenizer = None
_summary_model = None


def _get_summary_model():
    global _summary_tokenizer, _summary_model
    if _summary_model is None:
        _summary_tokenizer = AutoTokenizer.from_pretrained(_SUMMARY_MODEL_NAME)
        _summary_model = AutoModelForSeq2SeqLM.from_pretrained(_SUMMARY_MODEL_NAME)
    return _summary_tokenizer, _summary_model


def _summary_token_limits(word_count):
    max_new_tokens = min(130, max(15, word_count // 2))
    min_new_tokens = min(max_new_tokens - 1, max(8, word_count // 4))
    return max_new_tokens, min_new_tokens


def _summarize_chunk(text, max_new_tokens=130, min_new_tokens=30):
    tokenizer, model = _get_summary_model()
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=1024,
        padding=False,
    )
    summary_ids = model.generate(
        inputs.input_ids,
        attention_mask=inputs.attention_mask,
        max_new_tokens=max_new_tokens,
        min_new_tokens=min_new_tokens,
        num_beams=4,
        early_stopping=True,
        do_sample=False,
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)


def summarize_large_text(text):
    try:
        if not text or not text.strip():
            return "No text provided to summarize."

        word_count = len(text.split())
        if word_count < 40:
            return (
                "Text is too short to summarize reliably. "
                "Please enter at least 40–50 words (a short paragraph or more)."
            )

        chunks = split_into_chunks_spacy(text, max_length=500)
        if not chunks:
            return "No text to summarize after splitting."

        chunk_summaries = []
        for chunk in chunks:
            chunk_words = len(chunk.split())
            max_new, min_new = _summary_token_limits(chunk_words)
            chunk_summaries.append(_summarize_chunk(chunk, max_new, min_new))

        combined_summary_text = " ".join(chunk_summaries)
        if len(chunks) == 1:
            return combined_summary_text.strip()

        combined_words = len(combined_summary_text.split())
        max_new, min_new = _summary_token_limits(combined_words)
        return _summarize_chunk(combined_summary_text, max_new, min_new).strip()
    except Exception as e:
        return f"Summary failed: {e}"

