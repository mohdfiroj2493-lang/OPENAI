import streamlit as st
import pandas as pd
import numpy as np

from modules.ui import setup_page, source_card
from modules.answer_engine import research
from modules.search_tools import search_all, fetch_webpage_text, ddg_image_search
from modules.pdf_tools import fetch_pdf_text
from modules.doc_tools import extract_file_text, document_report
from modules.math_tools import solve_math, formula_sheet
from modules.csv_tools import csv_profile
from modules.text_utils import extract_key_points, extract_equations, clean_text

setup_page()

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {"role": "assistant", "content": "Ask me anything. I will search the internet, read sources, inspect online PDFs/reports, extract equations, and show figures where available."}
    ]

with st.sidebar:
    st.header("Navigation")
    mode = st.radio(
        "Choose tool",
        [
            "AI Research Chat",
            "Search Engine",
            "Source Reader",
            "Document Assistant",
            "CSV Analyzer",
            "Math & Formula Tools",
            "About",
        ],
    )
    st.divider()
    st.caption("No OpenAI/Claude API key is required. The app uses search, webpage/PDF extraction, and local summarization logic.")

if mode == "AI Research Chat":
    st.subheader("AI Research Chat")
    st.write("Ask a question. The app searches multiple queries, reads webpages/PDFs, filters irrelevant sources, extracts expressions, and shows figures.")

    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    question = st.chat_input("Ask any question...")
    if question:
        st.session_state.chat_messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching web, reading online PDFs/reports, extracting equations and figures..."):
                data = research(question, include_images=True)
            st.markdown(f"<div class='answer-card'>{data['answer']}</div>", unsafe_allow_html=True)
            if data.get("images"):
                st.markdown("### Related figures / images")
                cols = st.columns(4)
                for idx, img in enumerate(data["images"][:8]):
                    with cols[idx % 4]:
                        st.image(img.get("thumbnail") or img.get("image"), caption=img.get("title", "Figure"), use_container_width=True)
                        st.link_button("Open source", img.get("url", img.get("image", "")))
            if data.get("sources"):
                st.markdown("### Sources read")
                for i, src in enumerate(data["sources"][:8], start=1):
                    source_card(src, i)
            saved = data["answer"] + "\n\nSources:\n" + "\n".join([f"- {s.get('title')}: {s.get('url')}" for s in data.get("sources", [])[:8]])
            st.session_state.chat_messages.append({"role": "assistant", "content": saved})

elif mode == "Search Engine":
    st.subheader("Search Engine")
    q = st.text_input("Search the internet, PDFs, reports, or images")
    col1, col2, col3 = st.columns(3)
    with col1:
        show_web = st.checkbox("Web results", True)
    with col2:
        show_pdf = st.checkbox("PDF/report results", True)
    with col3:
        show_images = st.checkbox("Image/figure results", True)

    if st.button("Search", type="primary") and q:
        with st.spinner("Searching..."):
            results = search_all(q, max_per_query=8)
            images = ddg_image_search(q + " diagram figure", max_results=12) if show_images else []
        tabs = st.tabs(["Web/PDF Results", "Images/Figures"])
        with tabs[0]:
            filtered = []
            for r in results:
                if r.get("type") == "pdf" and show_pdf:
                    filtered.append(r)
                if r.get("type") != "pdf" and show_web:
                    filtered.append(r)
            for i, r in enumerate(filtered[:20], start=1):
                source_card(r, i)
        with tabs[1]:
            if images:
                cols = st.columns(4)
                for idx, img in enumerate(images):
                    with cols[idx % 4]:
                        st.image(img.get("thumbnail") or img.get("image"), caption=img.get("title", "Image"), use_container_width=True)
                        st.link_button("Open", img.get("url", img.get("image", "")))
            else:
                st.info("No image results found.")

elif mode == "Source Reader":
    st.subheader("Read and summarize a specific source")
    url = st.text_input("Paste webpage or PDF URL")
    focus = st.text_input("What should I focus on?", "summary equations methods conclusions")
    if st.button("Read source") and url:
        with st.spinner("Reading source..."):
            text = fetch_pdf_text(url) if url.lower().split("?")[0].endswith(".pdf") else fetch_webpage_text(url)
        if not text:
            st.error("Could not read this source. It may block automated reading or require login.")
        else:
            st.success(f"Read {len(text):,} characters.")
            points = extract_key_points(text, focus, n=18)
            eqs = extract_equations(text, max_items=20)
            st.markdown("### Summary")
            for p in points:
                st.markdown(f"- {p}")
            if eqs:
                st.markdown("### Equations / expressions found")
                for e in eqs:
                    st.code(e)
            with st.expander("Raw extracted text"):
                st.write(text[:20000])

elif mode == "Document Assistant":
    st.subheader("Document Assistant")
    uploaded = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    focus = st.text_input("Focus area", "important details, equations, conclusions, recommendations")
    if uploaded:
        with st.spinner("Extracting document text..."):
            text = extract_file_text(uploaded)
        st.success(f"Extracted about {len(text):,} characters.")
        if st.button("Analyze document", type="primary"):
            st.markdown(document_report(text, focus))
            eqs = extract_equations(text, max_items=30)
            if eqs:
                st.markdown("### Equations / expressions found")
                for e in eqs:
                    st.code(e)
            with st.expander("Raw extracted text"):
                st.write(text[:30000])

elif mode == "CSV Analyzer":
    st.subheader("CSV Analyzer")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    if uploaded:
        df = pd.read_csv(uploaded)
        st.dataframe(df, use_container_width=True)
        st.markdown(csv_profile(df))
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            col = st.selectbox("Chart numeric column", numeric_cols)
            st.bar_chart(df[col])

elif mode == "Math & Formula Tools":
    st.subheader("Math & Formula Tools")
    tab1, tab2 = st.tabs(["Solve Math", "Formula Sheet"])
    with tab1:
        expr = st.text_input("Enter expression or equation", "x**2 - 5*x + 6 = 0")
        if st.button("Solve"):
            st.markdown(solve_math(expr))
    with tab2:
        topic = st.text_input("Formula topic", "earth pressure")
        if st.button("Show formulas"):
            st.markdown(formula_sheet(topic))

elif mode == "About":
    st.subheader("About this application")
    st.markdown(
        """
        This is a no-API-key research assistant. It is designed to be much stronger than a simple Wikipedia app.

        **What it can do:**
        - Search multiple internet queries
        - Read public webpages
        - Read online PDFs when accessible
        - Filter irrelevant results
        - Extract equations and expressions
        - Show source links and relevance scores
        - Search for figures and diagrams
        - Analyze uploaded files
        - Analyze CSV files
        - Solve math expressions

        **Important limitation:**
        This is not a real LLM like ChatGPT or Claude. It cannot fully reason or write with the same quality unless you connect an LLM API or host a local model. This app is the strongest possible no-key web-research style assistant.
        """
    )
