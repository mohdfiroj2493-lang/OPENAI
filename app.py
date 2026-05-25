import re
import io
import math
import textwrap
from collections import Counter

import requests
import streamlit as st
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import wikipedia
import pandas as pd
import numpy as np
import sympy as sp
from pypdf import PdfReader
from docx import Document

st.set_page_config(page_title="Internet Research AI Assistant", page_icon="🌐", layout="wide")

CUSTOM_CSS = """
<style>
.main-title {font-size: 2.2rem; font-weight: 800; margin-bottom: 0.2rem;}
.subtitle {color: #666; font-size: 1rem; margin-bottom: 1.2rem;}
.answer-card {background: #ffffff; border: 1px solid #e8e8e8; border-radius: 18px; padding: 1.2rem; box-shadow: 0 2px 14px rgba(0,0,0,0.04);}
.source-card {background: #f8f9fb; border: 1px solid #ececec; border-radius: 14px; padding: 0.8rem; margin-bottom: 0.6rem;}
.small-muted {color: #777; font-size: 0.88rem;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

st.markdown('<div class="main-title">🌐 Internet Research AI Assistant</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Ask questions and get answers from web search results and public pages. No API key required.</div>', unsafe_allow_html=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
}

STOPWORDS = set("""
a an and are as at be by for from has have he in is it its of on or that the to was were will with you your i we they them this those these can could should would about into over under than then there their if but not no yes do does did done using use used more most many much such also other some any all each when where what why how who whom whose which write give explain define equation equations motion law formula formulas
""".split())


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def split_sentences(text: str):
    text = clean_text(text)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 30]


def keywords(query: str):
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", query.lower())
    return [w for w in words if w not in STOPWORDS]


def sentence_score(sentence: str, query_words):
    s = sentence.lower()
    score = 0
    for w in query_words:
        if w in s:
            score += 2
    score += min(len(sentence) / 180, 2)
    if any(x in s for x in ["formula", "equation", "defined", "states", "known as", "used to", "therefore", "because"]):
        score += 1.5
    return score


def summarize_text(text: str, query: str, max_sentences: int = 7):
    sentences = split_sentences(text)
    if not sentences:
        return "I found information, but I could not extract a readable answer from the page text."
    q_words = keywords(query)
    ranked = sorted(sentences, key=lambda s: sentence_score(s, q_words), reverse=True)
    selected = ranked[:max_sentences]
    selected = sorted(selected, key=lambda s: sentences.index(s))
    return "\n\n".join(selected)


def ddg_search(query: str, max_results: int = 8):
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title") or "Untitled"
                href = r.get("href") or r.get("url") or ""
                body = r.get("body") or ""
                if href:
                    results.append({"title": title, "url": href, "snippet": body})
    except Exception as e:
        st.warning(f"Search issue: {e}")
    return results


def fetch_page_text(url: str, timeout: int = 8):
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        if response.status_code >= 400:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        paragraphs = [clean_text(p.get_text(" ")) for p in soup.find_all(["p", "li", "h1", "h2", "h3"])]
        text = " ".join([p for p in paragraphs if len(p) > 40])
        return clean_text(text)[:12000]
    except Exception:
        return ""


def wikipedia_fallback(query: str):
    try:
        hits = wikipedia.search(query, results=3)
        if not hits:
            return None
        page = wikipedia.page(hits[0], auto_suggest=False)
        return {"title": page.title, "url": page.url, "text": page.content[:9000]}
    except Exception:
        return None


def research_answer(query: str):
    search_results = ddg_search(query, max_results=8)
    source_texts = []
    sources = []

    for result in search_results[:5]:
        page_text = fetch_page_text(result["url"])
        combined = clean_text((result.get("snippet", "") + " " + page_text).strip())
        if len(combined) > 120:
            source_texts.append(combined)
            sources.append(result)

    wiki = None
    if len(source_texts) < 2:
        wiki = wikipedia_fallback(query)
        if wiki:
            source_texts.append(wiki["text"])
            sources.append({"title": wiki["title"], "url": wiki["url"], "snippet": "Wikipedia fallback source"})

    if not source_texts:
        return "I could not find enough readable internet content for this question. Try rephrasing the question with more specific words.", sources

    full_text = "\n\n".join(source_texts)
    summary = summarize_text(full_text, query, max_sentences=8)

    intro = "Based on the internet sources I found, here is the best answer:\n\n"
    return intro + summary, sources


def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = []
    for page in reader.pages:
        text.append(page.extract_text() or "")
    return "\n".join(text)


def extract_docx_text(uploaded_file):
    doc = Document(uploaded_file)
    return "\n".join([p.text for p in doc.paragraphs])


def extract_txt_text(uploaded_file):
    return uploaded_file.read().decode("utf-8", errors="ignore")


def basic_document_summary(text):
    sentences = split_sentences(text)
    if not sentences:
        return "No readable text found."
    words = [w.lower() for w in re.findall(r"[a-zA-Z]{4,}", text) if w.lower() not in STOPWORDS]
    common = Counter(words).most_common(12)
    top_words = [w for w, _ in common]
    ranked = sorted(sentences, key=lambda s: sentence_score(s, top_words), reverse=True)[:8]
    ranked = sorted(ranked, key=lambda s: sentences.index(s))
    return "\n\n".join(ranked)


def solve_math(expr):
    try:
        x = sp.symbols("x")
        if "=" in expr:
            left, right = expr.split("=", 1)
            sol = sp.solve(sp.sympify(left) - sp.sympify(right), x)
            return f"Solution: {sol}"
        result = sp.sympify(expr)
        return f"Result: {sp.simplify(result)}"
    except Exception as e:
        return f"Could not solve that expression. Error: {e}"


if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! Ask me anything. I will search the internet and answer with sources."}
    ]

with st.sidebar:
    st.header("Tools")
    mode = st.radio(
        "Choose mode",
        ["Internet Chat", "Document Assistant", "CSV Analyzer", "Math Solver"],
        index=0,
    )
    st.caption("This app uses internet search and local tools, not OpenAI or Claude API keys.")

if mode == "Internet Chat":
    st.subheader("Ask from the internet")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask a question...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching the internet and reading sources..."):
                answer, sources = research_answer(question)
            st.markdown(f'<div class="answer-card">{answer}</div>', unsafe_allow_html=True)
            if sources:
                st.markdown("### Sources")
                for i, src in enumerate(sources[:6], start=1):
                    st.markdown(
                        f'<div class="source-card"><b>{i}. {src["title"]}</b><br><a href="{src["url"]}" target="_blank">{src["url"]}</a><br><span class="small-muted">{src.get("snippet", "")}</span></div>',
                        unsafe_allow_html=True,
                    )
            saved = answer + "\n\nSources:\n" + "\n".join([f"- {s['title']}: {s['url']}" for s in sources[:6]])
            st.session_state.messages.append({"role": "assistant", "content": saved})

elif mode == "Document Assistant":
    st.subheader("Upload and summarize documents")
    file = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    if file:
        with st.spinner("Reading document..."):
            if file.name.lower().endswith(".pdf"):
                text = extract_pdf_text(file)
            elif file.name.lower().endswith(".docx"):
                text = extract_docx_text(file)
            else:
                text = extract_txt_text(file)
        st.success(f"Extracted approximately {len(text):,} characters.")
        user_focus = st.text_input("Optional: what should I focus on in the summary?", "")
        if st.button("Summarize document"):
            query = user_focus or "summarize important information"
            st.markdown(basic_document_summary(text if not user_focus else text + " " + query))

elif mode == "CSV Analyzer":
    st.subheader("CSV data analyzer")
    file = st.file_uploader("Upload CSV", type=["csv"])
    if file:
        df = pd.read_csv(file)
        st.dataframe(df, use_container_width=True)
        st.markdown("### Summary")
        st.write(df.describe(include="all"))
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            col = st.selectbox("Choose numeric column for chart", numeric_cols)
            st.bar_chart(df[col])

elif mode == "Math Solver":
    st.subheader("Math solver")
    expr = st.text_input("Enter expression or equation, for example: x**2 - 5*x + 6 = 0")
    if st.button("Solve") and expr:
        st.markdown(solve_math(expr))
