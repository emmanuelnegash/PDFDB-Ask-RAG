import streamlit as st
from database import add_database, edit_database, get_table_names, load_credentials, save_credentials
from rag import OrganizationSystemChat
import tempfile
import os
import asyncio

# Load credentials at startup
if "databases" not in st.session_state:
    st.session_state["databases"] = load_credentials()

def display_sidebar():
    """Displays the sidebar with options to upload documents and connect to databases."""
    with st.sidebar:
        upload_button_label = "Show Upload Section" if st.session_state["hide_upload"] else "Hide Upload Section"
        db_button_label = "Show Database Connection" if st.session_state["hide_db_connect"] else "Hide Database Connection"

        if st.button(upload_button_label, key="toggle_upload"):
            st.session_state["hide_upload"] = not st.session_state["hide_upload"]
            st.experimental_rerun()

        if not st.session_state["hide_upload"]:
            display_upload_section()

        if st.button(db_button_label, key="toggle_db_connect"):
            st.session_state["hide_db_connect"] = not st.session_state["hide_db_connect"]
            st.experimental_rerun()

        if not st.session_state["hide_db_connect"]:
            display_database_section()

def display_upload_section():
    """Displays the document upload section."""
    st.subheader("Upload a document")
    uploaded_files = st.file_uploader(
        "Upload document",
        type=["pdf"],
        key="file_uploader",
        on_change=read_and_save_file,
        label_visibility="collapsed",
        accept_multiple_files=True,
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            file_info = {"name": uploaded_file.name, "data": uploaded_file.getbuffer()}
            cols = st.columns([5, 1])
            with cols[0]:
                if st.button(f"Open {uploaded_file.name}"):
                    st.session_state["selected_file"] = file_info
                    st.session_state["show_chat"] = True
                    st.session_state["show_db_chat"] = False
                    st.success(f"{uploaded_file.name} is selected for chat.")
            with cols[1]:
                if st.button("Delete", key=f"delete_{uploaded_file.name}"):
                    st.session_state["file_uploader"].remove(uploaded_file)
                    st.success(f"{uploaded_file.name} deleted.")

def display_database_section():
    """Displays the database connection section."""
    st.subheader("Connect to Database")
    for db in st.session_state["databases"]:
        cols = st.columns([5, 1])
        with cols[0]:
            connect_button = st.button(f"Chat with {db}", key=f"connect_{db}")
        with cols[1]:
            settings_button = st.button("⚙️", key=f"settings_{db}", help="Configure Database")

        if connect_button:
            reconnect_database(db)

        if settings_button:
            st.session_state.update({"selected_db": db, "show_edit_db_form": True})

    if st.button("Add New Database"):
        st.session_state["show_add_db_form"] = not st.session_state["show_add_db_form"]

    if st.session_state.get("show_add_db_form", False):
        display_add_db_form()

    if st.session_state.get("show_edit_db_form", False):
        display_edit_db_form()

def reconnect_database(db):
    """Handles reconnection to a database, fetching table names, and updating UI."""
    st.session_state["selected_db"] = db
    st.session_state["show_db_chat"] = True
    st.session_state["show_chat"] = False

    try:
        tables = get_table_names()
        if tables:
            st.session_state["db_tables"] = tables
            st.session_state["selected_tables"] = []  # Reset selected tables
            st.session_state["select_all_tables"] = False
        else:
            st.error("Failed to retrieve tables from the database.")
    except Exception as e:
        st.error(f"Error reconnecting to the database: {e}")

    st.experimental_rerun()

def display_add_db_form():
    """Displays the form to add a new database."""
    with st.form(key='add_db_form'):
        form_data = st.session_state.get("add_db_form_data", {})
        form_data["name"] = st.text_input("Database Name", value=form_data.get("name", ""))
        form_data["host"] = st.text_input("Host", value=form_data.get("host", ""))
        form_data["port"] = st.text_input("Port", value=form_data.get("port", ""))
        form_data["username"] = st.text_input("Username", value=form_data.get("username", ""))
        form_data["password"] = st.text_input("Password", value=form_data.get("password", ""), type="password")
        submitted = st.form_submit_button("Save Database")
        if submitted:
            if all(form_data.values()):
                try:
                    db_name, db_config = add_database(form_data)
                    if db_name and db_config:
                        st.session_state["databases"][db_name] = db_config
                        save_credentials(st.session_state["databases"])  # Save credentials
                        st.success(f"Database {db_name} added successfully!")
                    else:
                        st.error("Failed to add the database. Please check the credentials and try again.")
                    form_data.clear()
                    st.session_state["show_add_db_form"] = False
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Error adding the database: {e}")
            else:
                st.error("Please fill all the fields to add a new database.")

def display_edit_db_form():
    """Displays the form to edit an existing database configuration."""
    db_name = st.session_state["selected_db"]
    with st.form(key='edit_db_form'):
        db_config = st.session_state["databases"].get(db_name, {})
        form_data = st.session_state.get("edit_db_form_data", {})
        form_data["host"] = st.text_input("Host", value=db_config.get("host", ""))
        form_data["port"] = st.text_input("Port", value=db_config.get("port", ""))
        form_data["username"] = st.text_input("Username", value=db_config.get("username", ""))
        form_data["password"] = st.text_input("Password", value=db_config.get("password", ""), type="password")
        submitted = st.form_submit_button("Save Configuration")
        if submitted:
            try:
                db_name, db_config = edit_database(db_name, form_data, st.session_state["databases"])
                if db_name and db_config:
                    st.session_state["databases"][db_name] = db_config
                    save_credentials(st.session_state["databases"])  # Save credentials
                    st.success(f"Configuration for {db_name} saved successfully!")
                else:
                    st.error("Failed to edit the database. Please check the credentials and try again.")
                st.session_state["show_edit_db_form"] = False
                st.experimental_rerun()
            except Exception as e:
                st.error(f"Error editing the database: {e}")

async def read_and_save_file():
    """Reads and saves the uploaded files."""
    st.session_state["assistant"].clear()
    st.session_state["messages"] = []
    st.session_state["user_input"] = ""

    for file in st.session_state["file_uploader"]:
        if file is not None:
            try:
                with tempfile.NamedTemporaryFile(delete=False) as tf:
                    tf.write(file.getbuffer())
                    file_path = tf.name

                with st.spinner(f"Ingesting {file.name}"):
                    await st.session_state["assistant"].ingest_document(file_path)
                os.remove(file_path)
            except Exception as e:
                st.error(f"Error reading and saving file {file.name}: {e}")

# Add this function to handle the user input field for general chat
def handle_user_input():
    """Handles user input for chat and database queries."""
    if st.session_state["show_chat"]:
        process_input()
    elif st.session_state["show_db_chat"]:
        process_db_input()

# Updated display_messages function
def display_messages():
    """Displays the chat messages."""
    st.subheader("Chat")
    
    # Display user input field
    user_input = st.text_input("Enter your query", key="user_input", on_change=handle_user_input)
    
    # Display chat messages
    for i, (msg, is_user) in enumerate(st.session_state["messages"]):
        message(msg, is_user=is_user, key=str(i))
    
    st.session_state["thinking_spinner"] = st.empty()

# Updated display_db_messages function
def display_db_messages():
    """Displays the database chat messages."""
    db = st.session_state["selected_db"]
    st.subheader(f"Database Chat: {db}")
    
    if st.session_state["db_tables"]:
        st.checkbox("Select all tables", key="select_all_tables", on_change=select_all_tables)
        if st.session_state["select_all_tables"]:
            st.session_state["selected_tables"] = st.session_state["db_tables"]
        st.multiselect("Select tables to query", options=st.session_state["db_tables"], key="selected_tables")
    
    # Display user input field
    user_input = st.text_input("Enter your query", key="db_user_input", on_change=handle_user_input)
    
    # Display chat messages
    if db in st.session_state["db_messages"]:
        for i, (msg, is_user) in enumerate(st.session_state["db_messages"][db]):
            message(msg, is_user=is_user, key=f"{db}_{i}")
    
    st.session_state["db_thinking_spinner"] = st.empty()



def select_all_tables():
    """Select or deselect all tables."""
    if st.session_state["select_all_tables"]:
        st.session_state["selected_tables"] = st.session_state["db_tables"]
    else:
        st.session_state["selected_tables"] = []

def process_input():
    """Processes user input for chat queries."""
    user_input = st.session_state.get("user_input", "").strip()
    if user_input:
        try:
            with st.session_state["thinking_spinner"], st.spinner("Thinking"):
                agent_response = st.session_state["assistant"].ask(user_input)
            
            # Append user and agent messages to session state
            st.session_state["messages"].append((user_input, True))
            st.session_state["messages"].append((agent_response, False))
            
            # Clear user input
            st.session_state["user_input"] = ""
        except Exception as e:
            st.error(f"Error processing input: {e}")

def process_db_input():
    """Processes user input for database queries."""
    user_input = st.session_state.get("db_user_input", "").strip()
    if user_input:
        db_name = st.session_state["selected_db"]
        selected_tables = st.session_state["selected_tables"]
        table_text = ", ".join(selected_tables) if selected_tables else "No tables selected"

        try:
            with st.session_state["db_thinking_spinner"], st.spinner("Thinking"):
                ingestion_response = asyncio.run(st.session_state["assistant"].ingest_database(selected_tables))
                if ingestion_response:
                    st.error(ingestion_response)
                    agent_response = ingestion_response  # Ensure agent_response is defined in case of error
                else:
                    agent_response = st.session_state["assistant"].ask(user_input)
                    insights = st.session_state["assistant"].generate_insights(selected_tables, user_input)
                    agent_response += f"\n\nInsights: {insights}"

            # Append user and agent messages to session state
            if db_name not in st.session_state["db_messages"]:
                st.session_state["db_messages"][db_name] = []
            st.session_state["db_messages"][db_name].append((user_input, True))
            st.session_state["db_messages"][db_name].append((agent_response, False))
            
            st.session_state["rag_responses"].append(agent_response)  # Store RAG response

            # Clear user input
            st.session_state["db_user_input"] = ""
        except Exception as e:
            st.error(f"Error processing database input: {e}")

def display_rag_responses():
    """Displays the RAG (retrieval-augmented generation) responses."""
    if st.session_state["rag_responses"]:
        st.subheader("RAG Responses")
        for i, response in enumerate(st.session_state["rag_responses"]):
            st.markdown(f"**Response {i+1}:** {response}")

def message(msg, is_user=True, key=None):
    """Formats and displays a message."""
    if is_user:
        st.markdown(f"<div style='text-align: right; color: blue;'>{msg}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align: left; color: green;'>{msg}</div>", unsafe_allow_html=True)

def display_main_content():
    """Displays the main content area."""
    st.title("Main Content Area")
    display_rag_responses()
    handle_user_input()
    if st.session_state["show_chat"]:
        display_messages()
    elif st.session_state["show_db_chat"]:
        display_db_messages()

__all__ = ['display_sidebar', 'display_main_content', 'handle_user_input', 'display_messages', 'display_db_messages', 'display_rag_responses']
