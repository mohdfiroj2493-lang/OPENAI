import re
import textwrap
from datetime import datetime

import streamlit as st
import wikipedia
from sympy import sympify


st.set_page_config(
    page_title="No API Key AI Assistant",
    page_icon="🤖",
    layout="centered"
)

st.title("🤖 No API Key AI Assistant")
st.caption("Ask questions, calculate, summarize, and draft text without using an API key.")


SYSTEM_NOTE = """
This app does not use OpenAI, Claude, Gemini, or any paid API key.
Because of that, it will not be as powerful as Claude or ChatGPT.
It uses local rules, simple math, and Wikipedia lookup.
"""


if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi! I can answer many general questions without an API key. Try asking about a topic, calculation, summary, checklist, or email draft."
        }
    ]


if "show_note" not in st.session_state:
    st.session_state.show_note = True


with st.sidebar:
    st.header("About this app")
    st.info(SYSTEM_NOTE)
    st.subheader("Try these")
    examples = [
        "What is concrete slump test?",
        "Calculate 25 * 18 + 40",
        "Summarize: Soil compaction improves bearing capacity and reduces settlement.",
        "Write an email for project update",
        "Create a site inspection checklist",
    ]
    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state.pending_prompt = example

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "New chat started. Ask me anything."
            }
        ]
        st.rerun()


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_math_question(text: str) -> bool:
    lowered = text.lower().strip()
    math_words = ["calculate", "solve", "what is", "evaluate"]
    has_operator = bool(re.search(r"[0-9]\s*[+\-*/^()]\s*[0-9]", text))
    return has_operator or any(lowered.startswith(word) for word in math_words)


def answer_math(text: str) -> str | None:
    expr = text.lower()
    expr = expr.replace("calculate", "")
    expr = expr.replace("solve", "")
    expr = expr.replace("what is", "")
    expr = expr.replace("evaluate", "")
    expr = expr.replace("^", "**")
    expr = re.sub(r"[^0-9+\-*/().% **]", " ", expr)
    expr = clean_text(expr)

    if not expr or not re.search(r"\d", expr):
        return None

    try:
        result = sympify(expr)
        return f"The answer is:\n\n**{result}**"
    except Exception:
        return None


def summarize_text(text: str) -> str:
    text = re.sub(r"^summarize\s*:?", "", text, flags=re.IGNORECASE).strip()
    if not text:
        return "Please provide text after the word 'summarize'."

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 2:
        return "Summary:\n\n" + text

    summary = " ".join(sentences[:2])
    return "Summary:\n\n" + summary


def email_template(prompt: str) -> str:
    return textwrap.dedent(
        """
        Here is a professional email draft:

        **Subject:** Project Update

        Hi [Name],

        I hope you are doing well. I wanted to share a quick update regarding the project. We are continuing to make progress and will keep you informed of any important changes, pending items, or next steps.

        Please let me know if you have any questions or if there is anything else you would like us to include.

        Best regards,  
        [Your Name]
        """
    ).strip()


def checklist_template(prompt: str) -> str:
    return textwrap.dedent(
        """
        Here is a practical checklist:

        1. Review drawings, specifications, and project requirements.
        2. Confirm safety controls and site access.
        3. Check materials, equipment, and manpower.
        4. Verify field conditions against project documents.
        5. Document observations with notes and photos.
        6. Identify open issues, delays, or risks.
        7. Assign responsible parties for follow-up items.
        8. Share the report with the project team.
        """
    ).strip()


def definition_fallback(prompt: str) -> str:
    lowered = prompt.lower()

    built_in_answers = {
        "concrete slump test": "A concrete slump test checks the workability or consistency of fresh concrete. Fresh concrete is placed in a cone-shaped mold, the cone is lifted, and the amount the concrete settles is measured. A higher slump usually means the concrete is more workable or wetter.",
        "soil compaction": "Soil compaction is the process of increasing soil density by reducing air voids. It improves strength, bearing capacity, and stability while reducing settlement.",
        "spt": "SPT means Standard Penetration Test. It is a common geotechnical field test used to estimate soil resistance by counting hammer blows needed to drive a sampler into the soil.",
        "bearing capacity": "Bearing capacity is the ability of soil or rock to safely support loads from a foundation without excessive settlement or shear failure.",
        "rfi": "RFI means Request for Information. It is used in construction when clarification is needed about drawings, specifications, or project requirements.",
    }

    for key, value in built_in_answers.items():
        if key in lowered:
            return value

    return None


def wikipedia_answer(prompt: str) -> str | None:
    query = prompt
    query = re.sub(r"^(what is|who is|explain|define|tell me about)\s+", "", query, flags=re.IGNORECASE).strip(" ?")

    if len(query) < 3:
        return None

    try:
        wikipedia.set_lang("en")
        summary = wikipedia.summary(query, sentences=4, auto_suggest=True, redirect=True)
        return f"Here is what I found:\n\n{summary}\n\nSource: Wikipedia"
    except wikipedia.exceptions.DisambiguationError as e:
        options = e.options[:5]
        return "Your question is a little broad. Try one of these more specific topics:\n\n" + "\n".join(f"- {o}" for o in options)
    except Exception:
        return None


def general_assistant(prompt: str) -> str:
    lowered = prompt.lower().strip()

    math_answer = answer_math(prompt)
    if math_answer:
        return math_answer

    if lowered.startswith("summarize"):
        return summarize_text(prompt)

    if "email" in lowered or "mail" in lowered:
        return email_template(prompt)

    if "checklist" in lowered or "inspection" in lowered:
        return checklist_template(prompt)

    built_in = definition_fallback(prompt)
    if built_in:
        return built_in

    wiki = wikipedia_answer(prompt)
    if wiki:
        return wiki

    return textwrap.dedent(
        f"""
        I can help, but this no-API version has limited intelligence compared with Claude or ChatGPT.

        You asked: **{prompt}**

        Try asking in one of these formats:

        - `What is soil compaction?`
        - `Calculate 1500 * 0.12`
        - `Summarize: paste your text here`
        - `Write an email for project update`
        - `Create a site inspection checklist`
        """
    ).strip()


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])


prompt = st.chat_input("Ask anything...")

if "pending_prompt" in st.session_state:
    prompt = st.session_state.pending_prompt
    del st.session_state.pending_prompt


if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer = general_assistant(prompt)
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
