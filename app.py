"""Web UI for ClarifySQL, built with Streamlit.

Streamlit reruns this whole script top-to-bottom on every button click, so
the things that need to survive between clicks (the pending ambiguity
check, the generated SQL) are kept in st.session_state instead of local
variables.
"""
import streamlit as st
from groq import GroqError

from clarifysql.ambiguity_checker import apply_clarification, check_ambiguity
from clarifysql.db import run_query
from clarifysql.sql_generator import generate_sql


def generate(question):
    """generate_sql with a readable message instead of a traceback when the
    LLM service is down or rate-limited."""
    try:
        with st.spinner("Generating SQL..."):
            return generate_sql(question)
    except GroqError as e:
        st.error(f"The LLM service is busy or unreachable, please try again. ({type(e).__name__})")
        return None


st.set_page_config(page_title="ClarifySQL", page_icon="🗄️")
st.title("ClarifySQL")
st.caption("Ask a question about customers, orders or payments in plain English.")

if "question" not in st.session_state:
    st.session_state.question = ""
    st.session_state.check = None
    st.session_state.result = None

question = st.text_input("Your question", placeholder="e.g. Who is our best customer?")

if st.button("Ask") and question:
    st.session_state.question = question
    st.session_state.result = None
    with st.spinner("Checking the question..."):
        check = check_ambiguity(question)
    if check.is_ambiguous:
        st.session_state.check = check
    else:
        st.session_state.check = None
        st.session_state.result = generate(question)

if st.session_state.check:
    check = st.session_state.check
    st.info(check.clarification_question)
    labels = [option.label for option in check.options]
    choice = st.radio("Pick one:", labels)

    if st.button("Confirm and generate SQL"):
        chosen = check.options[labels.index(choice)]
        st.session_state.result = generate(apply_clarification(st.session_state.question, chosen))
        st.session_state.check = None

if st.session_state.result:
    result = st.session_state.result
    if result.failed_attempts:
        with st.expander(f"Self-corrected after {len(result.failed_attempts)} failed attempt(s)"):
            for attempt in result.failed_attempts:
                st.code(attempt.sql or "(no SQL returned)", language="sql")
                st.caption(attempt.error)

    if not result.ok:
        st.error(f"Could not produce a valid query: {result.error}")
    else:
        st.subheader("Generated SQL")
        st.code(result.sql, language="sql")
        st.caption(result.explanation)
        if st.button("Run query"):
            try:
                columns, rows = run_query(result.sql)
                st.dataframe([dict(zip(columns, row)) for row in rows])
            except Exception as e:
                st.error(f"The query failed: {e}")
