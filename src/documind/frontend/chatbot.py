import os
import time

import httpx
import streamlit as st

# Configuration
API_URL = os.getenv("API_URL", "http://api:8000")
POLL_INTERVAL = 1.0  # seconds

st.set_page_config(
    page_title="DocuMind Chatbot",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 DocuMind Chatbot")
st.markdown("Interact with your documents using DocuMind's Q&A agent.")

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_doc_id" not in st.session_state:
    st.session_state.current_doc_id = None

# Sidebar for document selection
with st.sidebar:
    st.header("Documents")
    try:
        response = httpx.get(f"{API_URL}/documents?limit=100")
        if response.status_code == 200:
            documents = response.json()
            if not documents:
                st.info("No documents found. Upload some via the API first.")
            else:
                doc_options = {doc["filename"]: doc["id"] for doc in documents}
                selected_filename = st.selectbox(
                    "Select a document to chat with:",
                    options=list(doc_options.keys()),
                )
                if selected_filename:
                    new_doc_id = doc_options[selected_filename]
                    if new_doc_id != st.session_state.current_doc_id:
                        st.session_state.current_doc_id = new_doc_id
                        st.session_state.messages = []  # Clear chat on document change
                        st.success(f"Selected: {selected_filename}")
        else:
            st.error(f"Failed to fetch documents: {response.status_code}")
    except Exception as e:
        st.error(f"Error connecting to API: {str(e)}")

    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "sources" in message:
            with st.expander("Sources"):
                for source in message["sources"]:
                    st.markdown(
                        f"**Page {source.get('page', 'N/A')}**: {source.get('content_preview')}"
                    )
                    st.markdown("---")

# Chat input
if prompt := st.chat_input("Ask a question about the document..."):
    if not st.session_state.current_doc_id:
        st.error("Please select a document from the sidebar first.")
    else:
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Send request to API
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            message_placeholder.markdown("⏳ Processing...")

            try:
                # 1. Start analysis task
                start_response = httpx.post(
                    f"{API_URL}/analysis",
                    json={
                        "document_id": st.session_state.current_doc_id,
                        "tasks": ["qa"],
                        "questions": [prompt],
                    },
                    timeout=30.0,
                )

                if start_response.status_code == 202:
                    task_id = start_response.json()["task_id"]

                    # 2. Poll for results
                    status = "queued"
                    while status in ["queued", "processing"]:
                        time.sleep(POLL_INTERVAL)
                        status_response = httpx.get(f"{API_URL}/analysis/{task_id}/status")
                        if status_response.status_code == 200:
                            status = status_response.json()["status"]
                        else:
                            st.error(f"Failed to check status: {status_response.status_code}")
                            break

                    if status == "completed":
                        # 3. Get results
                        results_response = httpx.get(f"{API_URL}/results/{task_id}")
                        if results_response.status_code == 200:
                            data = results_response.json()
                            qa_results = data.get("qa_results") or []
                            if qa_results:
                                result = qa_results[0]  # We only asked one question
                                answer = result["answer"]
                                sources = result.get("sources", [])
                                confidence = result.get("confidence", 0.0)

                                formatted_answer = f"{answer}\n\n*Confidence: {confidence:.2f}*"
                                message_placeholder.markdown(formatted_answer)

                                if sources:
                                    with st.expander("Sources"):
                                        for source in sources:
                                            st.markdown(
                                                f"**Page {source.get('page', 'N/A')}**: {source.get('content_preview')}"
                                            )
                                            st.markdown("---")

                                st.session_state.messages.append(
                                    {
                                        "role": "assistant",
                                        "content": formatted_answer,
                                        "sources": sources,
                                    }
                                )
                            else:
                                message_placeholder.markdown("No answer found.")
                        else:
                            message_placeholder.markdown(
                                f"⚠️ Error retrieving results: {results_response.status_code}"
                            )
                    else:
                        message_placeholder.markdown(f"⚠️ Analysis failed with status: {status}")
                else:
                    message_placeholder.markdown(
                        f"⚠️ Failed to start analysis: {start_response.status_code}"
                    )

            except Exception as e:
                message_placeholder.markdown(f"⚠️ Error: {str(e)}")
