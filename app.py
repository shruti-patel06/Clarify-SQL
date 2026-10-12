"""Web UI for ClarifySQL, built with Streamlit.

Streamlit reruns this whole script top-to-bottom on every button click, so
the things that need to survive between clicks (the pending ambiguity
check, the generated SQL) are kept in st.session_state instead of local
variables.
"""
import streamlit as st

from clarifysql.ambiguity_checker import check_ambiguity
from clarifysql.db import run_query
from clarifysql.sql_generator import generate_sql
from clarifysql.validator import is_safe

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
    check = check_ambiguity(question)
    if check.is_ambiguous:
        st.session_state.check = check
    else:
        st.session_state.check = None
        with st.spinner("Generating SQL..."):
            st.session_state.result = generate_sql(question)

if st.session_state.check:
    check = st.session_state.check
    st.info(check.clarification_question)
    labels = [option.label for option in check.options]
    choice = st.radio("Pick one:", labels)

    if st.button("Confirm and generate SQL"):
        chosen = next(o for o in check.options if o.label == choice)
        full_question = (
            f"{st.session_state.question} "
            f"(use this definition: {chosen.label} — {chosen.sql_hint})"
        )
        with st.spinner("Generating SQL..."):
            st.session_state.result = generate_sql(full_question)
        st.session_state.check = None

if st.session_state.result:
    result = st.session_state.result
    st.subheader("Generated SQL")
    st.code(result.sql, language="sql")
    st.caption(result.explanation)

    if not is_safe(result.sql):
        st.error("This query was blocked — it is not a plain SELECT statement.")
    elif st.button("Run query"):
        columns, rows = run_query(result.sql)
        st.dataframe([dict(zip(columns, row)) for row in rows])
