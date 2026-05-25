import io
import re
import textwrap
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import sympy as sp
import wikipedia
from docx import Document
from pypdf import PdfReader


st.set_page_config(
    page_title="Powerful No-API AI Assistant",
    page_icon="🧠",
    layout="wide",
)


# -----------------------------
# Utility functions
# -----------------------------

def clean_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_sentences(text: str):
    text = clean_text(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 20]


def keyword_summary(text: str, max_sentences: int = 6) -> str:
    sentences = split_sentences(text)
    if not sentences:
        return "I could not find enough readable text to summarize."

    stopwords = set("""
    the a an and or but if then else when where what who why how is are was were be been being
    of to in for on with as by from this that these those it its into about over under between
    can could should would may might will shall not no yes do does did done your you we they he she
    their our my his her them us i me at have has had there here also very more most many much
    """.split())

    words = re.findall(r"[A-Za-z]{3,}", text.lower())
    freq = Counter(w for w in words if w not in stopwords)
    if not freq:
        return "I could not identify enough keywords to summarize this text."

    scores = []
    for sentence in sentences:
        sentence_words = re.findall(r"[A-Za-z]{3,}", sentence.lower())
        score = sum(freq.get(w, 0) for w in sentence_words)
        scores.append((score, sentence))

    top = sorted(scores, reverse=True)[:max_sentences]
    selected = [s for _, s in top]
    # Preserve original order
    ordered = [s for s in sentences if s in selected]
    return "\n\n".join(f"- {s}" for s in ordered)


def extract_text_from_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def extract_text_from_docx(uploaded_file) -> str:
    document = Document(uploaded_file)
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs)


def extract_text_from_txt(uploaded_file) -> str:
    raw = uploaded_file.read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1", errors="ignore")


def safe_wikipedia_answer(query: str) -> str:
    try:
        results = wikipedia.search(query, results=5)
        if not results:
            return "I could not find a good Wikipedia result for that topic. Try using a more specific question."
        page_title = results[0]
        summary = wikipedia.summary(page_title, sentences=5, auto_suggest=False, redirect=True)
        return f"**Wikipedia result: {page_title}**\n\n{summary}"
    except wikipedia.DisambiguationError as e:
        options = e.options[:8]
        return "That topic is ambiguous. Try one of these:\n\n" + "\n".join(f"- {o}" for o in options)
    except Exception as e:
        return f"Wikipedia search failed: {e}"


def solve_math(question: str) -> str:
    text = question.strip()
    lowered = text.lower()

    try:
        # Equation solving examples: solve x^2 - 4 = 0
        if "solve" in lowered:
            expr_text = re.sub(r"(?i)solve", "", text).strip()
            expr_text = expr_text.replace("^", "**")
            x = sp.Symbol("x")
            if "=" in expr_text:
                left, right = expr_text.split("=", 1)
                equation = sp.Eq(sp.sympify(left), sp.sympify(right))
                solution = sp.solve(equation, x)
            else:
                solution = sp.solve(sp.sympify(expr_text), x)
            return f"Solution: `{solution}`"

        # Regular expression calculation
        expr = text.replace("^", "**")
        allowed = re.sub(r"[^0-9+\-*/().% xXabcdefghijklmnopqrstuvwxyz_= ]", "", expr)
        value = sp.sympify(allowed)
        simplified = sp.simplify(value)
        return f"Result: `{simplified}`"
    except Exception as e:
        return f"I could not solve that math expression. Try something like `2+2`, `sqrt(25)`, or `solve x^2 - 4 = 0`. Details: {e}"


def draft_email(prompt: str) -> str:
    topic = prompt.replace("write email", "").replace("email", "").strip(" :.-")
    if not topic:
        topic = "the topic we discussed"
    return f"""**Subject:** Follow-Up Regarding {topic.title()}

Hi [Name],

I hope you are doing well. I wanted to follow up regarding {topic}. Please let me know if you have any updates or if there is anything you need from my side.

Thank you,
[Your Name]"""


def create_checklist(prompt: str) -> str:
    topic = prompt.lower().replace("checklist", "").replace("create", "").replace("make", "").strip(" :.-")
    if not topic:
        topic = "project task"
    items = [
        f"Confirm the scope and objective for {topic}.",
        "Review drawings, specifications, or reference documents.",
        "Identify safety, quality, and schedule requirements.",
        "List responsible people and required approvals.",
        "Check materials, equipment, and access needs.",
        "Document observations with notes and photos.",
        "Track open issues and follow-up actions.",
        "Confirm completion and save final records.",
    ]
    return "\n".join(f"- [ ] {item}" for item in items)


def explain_code(code: str) -> str:
    lines = code.strip().splitlines()
    if not lines:
        return "Paste code and I will explain it."
    explanation = [f"This code has **{len(lines)} lines**."]
    if any("import " in line for line in lines):
        explanation.append("It imports external libraries or modules.")
    if any(line.strip().startswith("def ") for line in lines):
        funcs = [line.strip().split("(")[0].replace("def ", "") for line in lines if line.strip().startswith("def ")]
        explanation.append("Functions found: " + ", ".join(funcs))
    if any("st." in line for line in lines):
        explanation.append("It appears to be a Streamlit app or Streamlit component.")
    if any("for " in line or "while " in line for line in lines):
        explanation.append("It contains loops for repeated operations.")
    if any("try:" in line for line in lines):
        explanation.append("It includes error handling with try/except logic.")
    explanation.append("\n**First part of the code:**\n```python\n" + "\n".join(lines[:20]) + "\n```")
    return "\n\n".join(explanation)


def answer_question(question: str) -> str:
    q = question.strip()
    q_lower = q.lower()

    if not q:
        return "Please type a question."

    if q_lower.startswith("wiki ") or "wikipedia" in q_lower or q_lower.startswith("research "):
        query = q.replace("wiki", "").replace("wikipedia", "").replace("research", "").strip()
        return safe_wikipedia_answer(query or q)

    if any(word in q_lower for word in ["calculate", "solve", "sqrt", "sin", "cos", "tan"]) or re.fullmatch(r"[0-9+\-*/().%^ xX= ]+", q):
        cleaned = q_lower.replace("calculate", "").strip()
        return solve_math(cleaned)

    if "email" in q_lower:
        return draft_email(q)

    if "checklist" in q_lower:
        return create_checklist(q)

    if "summarize" in q_lower:
        text = q_lower.replace("summarize", "").strip()
        if len(text) > 100:
            return keyword_summary(text)
        return "Upload a PDF, DOCX, TXT, or paste longer text and I can summarize it."

    if any(word in q_lower for word in ["who is", "what is", "tell me about", "define", "explain"]):
        return safe_wikipedia_answer(q)

    return """I can help without an API key using built-in tools.

Try asking:

- `research Burj Khalifa`
- `calculate 25 * 48`
- `solve x^2 - 9 = 0`
- `write email about project delay`
- `create checklist for concrete pour inspection`
- Upload a PDF/DOCX/TXT and ask for a summary
- Upload a CSV and analyze the data

Because this version does not use OpenAI, Claude, or Gemini, it is not a true large language model. For Claude-level answers, a real AI API or locally hosted model is required."""


# -----------------------------
# App state
# -----------------------------

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I am your no-API AI assistant. I can research, calculate, summarize files, analyze CSVs, write emails, and create checklists."}
    ]


# -----------------------------
# Sidebar
# -----------------------------

with st.sidebar:
    st.title("🧠 No-API AI Tools")
    mode = st.radio(
        "Choose a tool",
        ["Chat", "Research", "File Summarizer", "CSV Analyzer", "Math Solver", "Email Writer", "Code Explainer"],
    )

    st.divider()
    st.info("No API key required. This app uses local Python tools and Wikipedia.")

    if st.button("Clear Chat"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Chat cleared. Ask me anything."}
        ]
        st.rerun()


st.title("🧠 Powerful No-API AI Assistant")
st.caption("A Streamlit assistant that works without OpenAI, Claude, Gemini, or paid API keys.")


# -----------------------------
# Chat mode
# -----------------------------

if mode == "Chat":
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask anything...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        answer = answer_question(prompt)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)


# -----------------------------
# Research mode
# -----------------------------

elif mode == "Research":
    st.subheader("Wikipedia Research Assistant")
    query = st.text_input("Enter a topic")
    if st.button("Research") and query:
        st.markdown(safe_wikipedia_answer(query))


# -----------------------------
# File summarizer
# -----------------------------

elif mode == "File Summarizer":
    st.subheader("Summarize PDF, DOCX, or TXT")
    uploaded = st.file_uploader("Upload a file", type=["pdf", "docx", "txt"])
    max_sentences = st.slider("Summary length", 3, 12, 6)

    if uploaded:
        try:
            if uploaded.name.lower().endswith(".pdf"):
                text = extract_text_from_pdf(uploaded)
            elif uploaded.name.lower().endswith(".docx"):
                text = extract_text_from_docx(uploaded)
            else:
                text = extract_text_from_txt(uploaded)

            st.success(f"Extracted approximately {len(text):,} characters.")
            with st.expander("Preview extracted text"):
                st.write(text[:4000])

            st.markdown("### Summary")
            st.markdown(keyword_summary(text, max_sentences=max_sentences))

            st.markdown("### Top Keywords")
            words = re.findall(r"[A-Za-z]{4,}", text.lower())
            common = Counter(words).most_common(20)
            if common:
                st.dataframe(pd.DataFrame(common, columns=["Keyword", "Count"]), use_container_width=True)
        except Exception as e:
            st.error(f"Could not process file: {e}")


# -----------------------------
# CSV analyzer
# -----------------------------

elif mode == "CSV Analyzer":
    st.subheader("Analyze CSV Data")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])

    if uploaded:
        try:
            df = pd.read_csv(uploaded)
            st.markdown("### Data Preview")
            st.dataframe(df.head(100), use_container_width=True)

            st.markdown("### Basic Information")
            col1, col2, col3 = st.columns(3)
            col1.metric("Rows", f"{df.shape[0]:,}")
            col2.metric("Columns", f"{df.shape[1]:,}")
            col3.metric("Missing Cells", f"{int(df.isna().sum().sum()):,}")

            st.markdown("### Numeric Summary")
            numeric = df.select_dtypes(include=np.number)
            if not numeric.empty:
                st.dataframe(numeric.describe().T, use_container_width=True)

                chart_col = st.selectbox("Select numeric column to chart", numeric.columns)
                fig, ax = plt.subplots()
                ax.hist(df[chart_col].dropna(), bins=20)
                ax.set_title(f"Distribution of {chart_col}")
                ax.set_xlabel(chart_col)
                ax.set_ylabel("Frequency")
                st.pyplot(fig)
            else:
                st.info("No numeric columns found.")

            st.markdown("### Missing Values")
            missing = df.isna().sum().reset_index()
            missing.columns = ["Column", "Missing Values"]
            st.dataframe(missing, use_container_width=True)
        except Exception as e:
            st.error(f"Could not analyze CSV: {e}")


# -----------------------------
# Math solver
# -----------------------------

elif mode == "Math Solver":
    st.subheader("Calculator and Equation Solver")
    expr = st.text_input("Enter expression", placeholder="Example: solve x^2 - 9 = 0 or 25*48")
    if st.button("Solve") and expr:
        st.markdown(solve_math(expr))


# -----------------------------
# Email writer
# -----------------------------

elif mode == "Email Writer":
    st.subheader("Professional Email Writer")
    topic = st.text_area("What should the email be about?")
    tone = st.selectbox("Tone", ["Professional", "Friendly", "Firm", "Apologetic"])
    if st.button("Generate Email") and topic:
        st.markdown(f"**Tone:** {tone}")
        st.markdown(draft_email(topic))


# -----------------------------
# Code explainer
# -----------------------------

elif mode == "Code Explainer":
    st.subheader("Code Explainer")
    code = st.text_area("Paste your code", height=300)
    if st.button("Explain Code") and code:
        st.markdown(explain_code(code))
