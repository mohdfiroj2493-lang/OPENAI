import io
import re
import math
import textwrap
from collections import Counter

import numpy as np
import pandas as pd
import requests
import streamlit as st
import wikipedia
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from pypdf import PdfReader
from docx import Document
import sympy as sp
import matplotlib.pyplot as plt

try:
    import trafilatura
except Exception:
    trafilatura = None


st.set_page_config(
    page_title="Powerful Research AI Assistant",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .main-title {
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #666;
        font-size: 1.05rem;
        margin-bottom: 1.2rem;
    }
    .answer-card {
        background: #ffffff;
        border: 1px solid #e7e7e7;
        border-radius: 18px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 6px 24px rgba(0,0,0,0.04);
        margin-bottom: 1rem;
    }
    .source-card {
        background: #f8f9fb;
        border: 1px solid #ececec;
        border-radius: 14px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.6rem;
    }
    .small-muted { color: #777; font-size: 0.9rem; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


STOPWORDS = set("""
a an the and or but if then else when while with without about above below from into onto over under again further more most less least very just also only same such than too can will shall may might must should would could in on at by to for of as is are was were be been being this that these those it its you your we our they their he she his her them i me my mine not no yes do does did done have has had having because since so what which who whom whose where why how any all each few many much some other own up down out off there here
""".split())

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StreamlitResearchAssistant/1.0; +https://streamlit.io)"
}


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\[[0-9]+\]", "", text)
    return text.strip()


def split_sentences(text: str):
    text = clean_text(text)
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 30]


def keywords(query: str):
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", query.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


def summarize_text(text: str, query: str = "", max_sentences: int = 8) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return "I could not find enough readable text to summarize."

    query_words = keywords(query)
    all_words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]+", text.lower()) if w not in STOPWORDS]
    freq = Counter(all_words)

    scored = []
    for idx, sent in enumerate(sentences):
        sent_words = re.findall(r"[A-Za-z][A-Za-z0-9_-]+", sent.lower())
        score = sum(freq.get(w, 0) for w in sent_words if w not in STOPWORDS)
        score += 12 * sum(1 for w in query_words if w in sent.lower())
        score += max(0, 4 - idx * 0.05)
        scored.append((score, idx, sent))

    top = sorted(scored, reverse=True)[:max_sentences]
    top = sorted(top, key=lambda x: x[1])
    return "\n\n".join(f"- {s}" for _, _, s in top)


def make_structured_answer(query: str, combined_text: str, sources=None):
    summary = summarize_text(combined_text, query, max_sentences=9)
    key_terms = keywords(query)[:8]

    intro = f"Here is a research-style answer for: **{query}**"
    limitations = "This app uses public web/document content and rule-based summarization. It does not use a paid LLM API, so it may be less fluent than Claude or ChatGPT."

    answer = f"""
<div class='answer-card'>

### 🚀 Answer

{intro}

### Key points

{summary}

### Practical takeaway

- Focus on the most repeated and source-supported ideas above.
- Review the sources below before using this for important work.
- For professional, legal, medical, or financial decisions, verify with authoritative sources.

### Search focus

{', '.join(key_terms) if key_terms else 'General topic analysis'}

<p class='small-muted'>{limitations}</p>

</div>
"""
    return answer


@st.cache_data(show_spinner=False, ttl=3600)
def search_web(query: str, max_results: int = 6):
    results = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                title = item.get("title") or "Untitled"
                href = item.get("href") or item.get("url") or ""
                body = item.get("body") or ""
                if href:
                    results.append({"title": title, "url": href, "snippet": body})
    except Exception as e:
        results.append({"title": "Search error", "url": "", "snippet": str(e)})
    return results


@st.cache_data(show_spinner=False, ttl=3600)
def fetch_page_text(url: str, timeout: int = 10):
    try:
        if trafilatura:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                extracted = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
                if extracted and len(extracted) > 300:
                    return clean_text(extracted)[:8000]

        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(" ")
        return clean_text(text)[:8000]
    except Exception:
        return ""


@st.cache_data(show_spinner=False, ttl=3600)
def wiki_lookup(query: str):
    try:
        results = wikipedia.search(query, results=3)
        if not results:
            return "", []
        pages = []
        chunks = []
        for title in results[:2]:
            try:
                page = wikipedia.page(title, auto_suggest=False)
                pages.append({"title": page.title, "url": page.url, "snippet": page.summary[:350]})
                chunks.append(page.content[:6000])
            except Exception:
                continue
        return "\n\n".join(chunks), pages
    except Exception:
        return "", []


def read_pdf(file):
    reader = PdfReader(file)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return clean_text("\n".join(pages))


def read_docx(file):
    doc = Document(file)
    text = "\n".join(p.text for p in doc.paragraphs)
    return clean_text(text)


def read_txt(file):
    return clean_text(file.read().decode("utf-8", errors="ignore"))


def solve_math(expr: str):
    try:
        if "=" in expr:
            left, right = expr.split("=", 1)
            x = sp.symbols("x")
            sol = sp.solve(sp.Eq(sp.sympify(left), sp.sympify(right)), x)
            return f"Solution: {sol}"
        value = sp.sympify(expr)
        return f"Result: {sp.N(value)}"
    except Exception as e:
        return f"Could not solve this expression. Error: {e}"


def draft_email(topic: str):
    return f"""Subject: {topic}

Hi [Name],

I hope you are doing well. I wanted to reach out regarding {topic.lower()}.

Please let me know your thoughts when you have a chance. I am happy to provide any additional information needed.

Best regards,
[Your Name]
"""


def generate_checklist(topic: str):
    items = [
        f"Define the objective for {topic}.",
        "Collect all required documents and background information.",
        "Confirm stakeholders, deadlines, and responsibilities.",
        "Review risks, assumptions, and constraints.",
        "Prepare the first draft or action plan.",
        "Check quality, accuracy, and completeness.",
        "Share with the team/client for review.",
        "Track comments, revisions, and final approval.",
    ]
    return "\n".join(f"- [ ] {item}" for item in items)


def classify_intent(prompt: str):
    p = prompt.lower().strip()
    if any(w in p for w in ["calculate", "solve", "equation", "math", "+", "*", "/"]):
        return "math"
    if any(w in p for w in ["email", "mail", "message to"]):
        return "email"
    if any(w in p for w in ["checklist", "steps", "todo", "to-do"]):
        return "checklist"
    return "research"


with st.sidebar:
    st.header("Tools")
    mode = st.radio(
        "Choose mode",
        ["Research Chat", "Document Assistant", "CSV Analyzer", "Math Solver", "Email Writer", "Checklist Generator"],
    )
    st.divider()
    st.write("**No API key required**")
    st.caption("Uses web search, public pages, Wikipedia fallback, and local document tools.")
    max_sources = st.slider("Web sources to read", 2, 8, 5)

st.markdown("<div class='main-title'>🚀 Powerful Research AI Assistant</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>No API key. Searches public web pages, reads documents, analyzes CSV files, solves math, and creates useful drafts.</div>", unsafe_allow_html=True)

if "chat" not in st.session_state:
    st.session_state.chat = []

if mode == "Research Chat":
    st.subheader("Ask a question")
    query = st.chat_input("Example: Explain mat foundation design, latest AI trends, concrete curing methods...")

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"], unsafe_allow_html=True)

    if query:
        st.session_state.chat.append({"role": "user", "content": query})
        with st.chat_message("user"):
            st.write(query)

        with st.chat_message("assistant"):
            intent = classify_intent(query)
            if intent == "math":
                result = solve_math(query.replace("calculate", "").replace("solve", ""))
                st.markdown(f"<div class='answer-card'>### 🧮 Math result\n\n{result}</div>", unsafe_allow_html=True)
                st.session_state.chat.append({"role": "assistant", "content": result})
            elif intent == "email":
                result = draft_email(query)
                st.code(result)
                st.session_state.chat.append({"role": "assistant", "content": result})
            elif intent == "checklist":
                result = generate_checklist(query)
                st.markdown(result)
                st.session_state.chat.append({"role": "assistant", "content": result})
            else:
                with st.spinner("Searching and reading public web content..."):
                    web_results = search_web(query, max_sources)
                    page_texts = []
                    source_cards = []
                    for item in web_results:
                        text = fetch_page_text(item["url"]) if item.get("url") else ""
                        if text:
                            page_texts.append(text)
                        if item.get("url"):
                            source_cards.append(item)

                    wiki_text, wiki_sources = wiki_lookup(query)
                    if wiki_text:
                        page_texts.append(wiki_text)
                        source_cards.extend(wiki_sources)

                    combined = "\n\n".join(page_texts) if page_texts else "\n".join(r.get("snippet", "") for r in web_results)
                    answer_html = make_structured_answer(query, combined, source_cards)
                    st.markdown(answer_html, unsafe_allow_html=True)

                    if source_cards:
                        st.markdown("### Sources")
                        for i, src in enumerate(source_cards[:max_sources], 1):
                            st.markdown(
                                f"<div class='source-card'><b>{i}. {src.get('title','Source')}</b><br>"
                                f"<a href='{src.get('url','#')}' target='_blank'>{src.get('url','')}</a><br>"
                                f"<span class='small-muted'>{src.get('snippet','')[:250]}</span></div>",
                                unsafe_allow_html=True,
                            )
                    else:
                        st.info("No sources were found. Try a more specific question.")

                    st.session_state.chat.append({"role": "assistant", "content": answer_html})

elif mode == "Document Assistant":
    st.subheader("Upload a PDF, DOCX, or TXT file")
    uploaded = st.file_uploader("Upload document", type=["pdf", "docx", "txt"])
    question = st.text_input("What do you want from the document?", "Summarize this document")

    if uploaded and st.button("Analyze document"):
        with st.spinner("Reading document..."):
            if uploaded.name.lower().endswith(".pdf"):
                text = read_pdf(uploaded)
            elif uploaded.name.lower().endswith(".docx"):
                text = read_docx(uploaded)
            else:
                text = read_txt(uploaded)

            st.markdown(make_structured_answer(question, text), unsafe_allow_html=True)
            with st.expander("Extracted text preview"):
                st.write(text[:5000])

elif mode == "CSV Analyzer":
    st.subheader("Upload a CSV file")
    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df = pd.read_csv(csv_file)
        st.dataframe(df, use_container_width=True)
        st.markdown("### Quick analysis")
        st.write(f"Rows: **{df.shape[0]}**, Columns: **{df.shape[1]}**")
        st.write("Columns:", list(df.columns))
        st.dataframe(df.describe(include="all").transpose(), use_container_width=True)

        numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
        if numeric_cols:
            col = st.selectbox("Chart column", numeric_cols)
            fig, ax = plt.subplots()
            df[col].dropna().hist(ax=ax, bins=20)
            ax.set_title(f"Distribution of {col}")
            ax.set_xlabel(col)
            ax.set_ylabel("Count")
            st.pyplot(fig)

elif mode == "Math Solver":
    st.subheader("Math calculator and equation solver")
    expr = st.text_input("Enter expression or equation", "2*x + 5 = 15")
    if st.button("Solve"):
        st.success(solve_math(expr))

elif mode == "Email Writer":
    st.subheader("Email writer")
    topic = st.text_input("Email topic", "Follow up on project meeting")
    tone = st.selectbox("Tone", ["Professional", "Friendly", "Direct", "Formal"])
    if st.button("Create email"):
        email = draft_email(topic)
        st.code(email)

elif mode == "Checklist Generator":
    st.subheader("Checklist generator")
    topic = st.text_input("Checklist topic", "Site inspection")
    if st.button("Create checklist"):
        st.markdown(generate_checklist(topic))
