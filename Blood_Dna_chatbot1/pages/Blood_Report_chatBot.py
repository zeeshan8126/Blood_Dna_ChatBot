import streamlit as st
from database.db import get_medical_data_by_id, save_chat, get_chat_history, clear_chat_history
from models.llm import generate_chat_response
from prompts.blood_report_chatbot_prompt import BLOOD_REPORT_PROMPT
from utils.logger import setup_logger

logger = setup_logger('blood_chatbot')

st.title("🩸 Blood Report Analysis Chatbot")

# Initialize chat history in session state if not present
if 'chat_messages' not in st.session_state:
    st.session_state.chat_messages = []

if 'processed_name' not in st.session_state or 'current_id' not in st.session_state:
    logger.warning("No processed name or ID found in session state")
    st.warning("Please process reports first")
    st.stop()

current_id = st.session_state.current_id
name = st.session_state.processed_name
logger.info(f"Loading blood reports for user ID: {current_id}")

# Get blood reports
total_reports, _ = get_medical_data_by_id(current_id) or ([], None)
blood_reports = [r for r in total_reports if r[2] == "blood"]
logger.info(f"Found {len(blood_reports)} blood reports")

# Display reports
with st.expander("🔍 View Extracted Blood Data"):
    if blood_reports:
        for report in blood_reports:
            st.write(f"**{report[2].upper()} Report ({report[5]})**")
            st.write(report[4])
            st.divider()
    else:
        logger.warning("No blood reports found")
        st.write("No blood reports found")

# Load chat history from database if session state is empty
if len(st.session_state.chat_messages) == 0:
    chat_history = get_chat_history(name, "blood")
    if chat_history:
        for chat in chat_history:
            st.session_state.chat_messages.extend([
                {"role": "user", "content": chat["question"]},
                {"role": "assistant", "content": chat["response"]}
            ])

# Create chat container
chat_container = st.container()

# Display chat history
with chat_container:
    for message in st.session_state.chat_messages:
        if message["role"] == "user":
            st.write("👤 **You:** " + message["content"])
        else:
            st.write("🤖 **Assistant:** " + message["content"])
    
    # Create a placeholder for new messages
    if 'message_placeholder' not in st.session_state:
        st.session_state.message_placeholder = st.empty()

# Chat input interface
user_input = st.chat_input("Ask about blood analysis...")

if user_input:
    logger.info(f"Processing user input: {user_input[:100]}...")
    context = "\n".join([f"Report {idx+1}:\n{report[4]}" for idx, report in enumerate(blood_reports)])
    
    messages = [{
        "role": "system",
        "content": f"{BLOOD_REPORT_PROMPT}\n\nContext:\n{context}"
    }, {
        "role": "user",
        "content": user_input
    }]
    
    with st.spinner("🔬 Analyzing Blood Report..."):
        response = generate_chat_response(messages, chat_type="blood")
        if response:
            chat_id = save_chat(name, "blood", user_input, response)
            logger.info(f"Saved chat response with ID: {chat_id}")
            
            # Add new messages to session state
            st.session_state.chat_messages.extend([
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": response}
            ])
            
            # Clear the message placeholder and rewrite all messages
            st.session_state.message_placeholder.empty()
            with chat_container:
                for message in st.session_state.chat_messages:
                    if message["role"] == "user":
                        st.write("👤 **You:** " + message["content"])
                    else:
                        st.write("🤖 **Assistant:** " + message["content"])

# Add clear chat button at the bottom
if st.button("Clear Chat History"):
    cleared_count = clear_chat_history(name, "blood")
    logger.info(f"Cleared {cleared_count} messages from chat history")
    st.session_state.chat_messages = []
    st.session_state.message_placeholder.empty()
    st.rerun()