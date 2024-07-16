import streamlit as st
from ui import display_sidebar, display_main_content
from database import load_credentials
from rag import OrganizationSystemChat

def initialize_session_state():
    """
    Initialize the session state variables with default values.
    """
    session_state_defaults = {
        "messages": [],
        "assistant": None,
        "selected_file": None,
        "show_chat": False,
        "db_messages": {},
        "selected_db": None,
        "show_db_chat": False,
        "hide_upload": True,
        "hide_db_connect": True,
        "databases": load_credentials(),  # Load saved databases
        "add_db_form_data": {},
        "edit_db_form_data": {},
        "show_add_db_form": False,
        "show_edit_db_form": False,
        "user_input": "",
        "db_user_input": "",
        "db_tables": [],
        "selected_tables": [],
        "select_all_tables": False,
        "rag_responses": []
    }
    
    for key, default in session_state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
    
    # Initialize the assistant separately to handle potential errors
    if "assistant" not in st.session_state or st.session_state["assistant"] is None:
        try:
            st.session_state["assistant"] = OrganizationSystemChat()
        except Exception as e:
            st.error(f"Error initializing assistant: {e}")
            st.session_state["assistant"] = None

def main():
    """
    Main function to run the Streamlit application.
    """
    st.set_page_config(page_title="ChatPDF", layout="wide")
    st.header("ChatPDF")
    
    initialize_session_state()  # Initialize session state variables

    display_sidebar()
    display_main_content()

if __name__ == "__main__":
    main()
