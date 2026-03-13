import streamlit as st
import os
import time
from src.graph import create_ase_graph
from src.tools.github_tools import GitHubTool
from dotenv import load_dotenv

# Load env but also allow manual override in sidebar
load_dotenv()

st.set_page_config(
    page_title="Ghost Coder | Autonomous Agent",
    page_icon="👻",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom Styling ---
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #4b0082;
        color: white;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #6a0dad;
        border: 1px solid #9370db;
    }
    .agent-card {
        padding: 1.5rem;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 1rem;
    }
    .status-text {
        font-size: 0.9rem;
        color: #888;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar Configuration ---
with st.sidebar:
    st.image("https://img.icons8.com/plasticine/100/000000/ghost.png", width=80)
    st.title("Settings")
    
    st.markdown("### API Keys")
    gh_token = st.text_input("GitHub Token", value=os.getenv("GITHUB_TOKEN", ""), type="password")
    groq_key = st.text_input("Groq API Key", value=os.getenv("GROQ_API_KEY", ""), type="password")
    
    if gh_token: os.environ["GITHUB_TOKEN"] = gh_token
    if groq_key: os.environ["GROQ_API_KEY"] = groq_key
    
    st.divider()
    st.markdown("### 3-Agent Core")
    st.info("Currently running in minimalist mode: Researcher -> Coder -> Tester")

# --- Main UI ---
st.title("👻 Ghost Coder")
st.markdown("#### Autonomous Software Engineering Orchestrator")

col1, col2 = st.columns([2, 1])

with col1:
    issue_url = st.text_input("Issue URL", placeholder="https://github.com/owner/repo/issues/123")
    
    if st.button("🚀 Execute Autonomous Fix"):
        if not issue_url:
            st.warning("Please provide a GitHub Issue URL.")
        elif not os.getenv("GITHUB_TOKEN") or not os.getenv("GROQ_API_KEY"):
            st.error("Missing API keys. Please set them in the sidebar or .env file.")
        else:
            gh_tool = GitHubTool()
            
            with st.status("Initializing Environment...", expanded=True) as status:
                st.write("🔍 Fetching issue metadata...")
                issue_info = gh_tool.fetch_issue_details(issue_url)
                
                if "Error" in issue_info['title']:
                    st.error(f"Failed to fetch issue: {issue_info['body']}")
                    st.stop()
                
                st.write(f"**Targeting:** {issue_info['title']}")
                
                workspace_dir = os.path.abspath("./workspace_clones/target_repo")
                st.write("📂 Cloning repository to workspace...")
                if not gh_tool.clone_repository(issue_url, workspace_dir):
                    st.error("Failed to clone repository. Workspace may be locked.")
                    st.stop()
                
                # --- Orchestration ---
                st.write("⚡ Starting agent orchestration...")
                
                initial_state = {
                    "issue_url": issue_url,
                    "issue_description": f"{issue_info['title']}\n\n{issue_info['body']}",
                    "repo_path": workspace_dir,
                    "files_to_modify": [],
                    "research_summary": "",
                    "updated_code": {},
                    "test_logs": "",
                    "test_passed": False,
                    "test_explanation": "",
                    "validation_attempts": 0
                }
                
                graph = create_ase_graph()
                final_state = None
                
                for output in graph.stream(initial_state):
                    for node_name, state_update in output.items():
                        icon = "📁" if node_name == "researcher" else "💻" if node_name == "coder" else "🧪"
                        st.subheader(f"{icon} {node_name.capitalize()} Agent Output")
                        
                        if node_name == "researcher" and state_update.get("research_summary"):
                            st.markdown(state_update["research_summary"])
                        
                        if node_name == "coder" and state_update.get("updated_code"):
                            for file, code in state_update["updated_code"].items():
                                st.markdown(f"**Fixed File:** `{file}`")
                                st.code(code, language="python")
                            if state_update.get("test_script"):
                                st.markdown("**Generated Test Case:**")
                                st.code(state_update["test_script"], language="python")
                        
                        if node_name == "tester":
                            if state_update.get("test_passed"):
                                st.success("✅ Tests Passed in Docker Sandbox!")
                                if state_update.get("test_logs"):
                                    with st.expander("View Execution Logs"):
                                        st.code(state_update["test_logs"], language="bash")
                            else:
                                st.error("❌ Tests Failed")
                                if state_update.get("test_explanation"):
                                    st.warning(f"**Feedback for Coder:** {state_update['test_explanation']}")
                        
                        final_state = state_update
                
                if final_state and final_state.get("test_passed"):
                    status.update(label="✅ Success! Issue Fixed.", state="complete")
                    st.success("Issue resolved and verified by automated tests!")
                    st.balloons()
                else:
                    status.update(label="❌ Failed after multiple attempts.", state="error")

with col2:
    st.markdown("### Agent Activity")
    if 'final_state' in locals() and final_state:
        st.info(f"Attempts: {final_state.get('validation_attempts', 0)}")
        if final_state.get("test_logs"):
            with st.expander("Test Results"):
                st.code(final_state["test_logs"], language="bash")
    else:
        st.write("No active session.")
