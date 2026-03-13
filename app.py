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
                final_state = initial_state.copy()
                
                for output in graph.stream(initial_state):
                    for node_name, state_update in output.items():
                        # Update cumulative state
                        final_state.update(state_update)
                        
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
                        
                        final_state.update(state_update)
                
                if final_state and final_state.get("test_passed"):
                    status.update(label="✅ Success! Issue Fixed.", state="complete")
                    st.success("Issue resolved and verified by automated tests!")
                    st.balloons()
                    
                    # Persist state for PR pipeline
                    st.session_state.final_state = final_state
                    if "pr_step" not in st.session_state:
                        st.session_state.pr_step = "branching"
                else:
                    status.update(label="❌ Failed after multiple attempts.", state="error")

    # --- HUMAN-IN-THE-LOOP DEPLOYMENT PIPELINE ---
    if st.session_state.get("final_state") and st.session_state.final_state.get("test_passed"):
        st.divider()
        st.header("🚀 Deployment Pipeline (Human-in-the-Loop)")
        
        final_state = st.session_state.final_state
        gh_tool = GitHubTool()
        repo_path = final_state["repo_path"]
        issue_url = final_state["issue_url"]
        files_to_update = list(final_state["updated_code"].keys())
        
        # --- STEP 1: BRANCH & STAGE ---
        if st.session_state.pr_step == "branching":
            st.warning(f"⚠️ **Target Verification:** You are about to stage changes for **{issue_url}**.")
            st.write(f"Files to be staged: `{files_to_update}`")
            
            if st.button("Confirm Target & Stage Changes"):
                # Use issue ID for branch name
                issue_id = issue_url.split('/')[-1]
                branch_name = f"ghost-fix-{issue_id}"
                st.session_state.branch_name = branch_name
                
                with st.spinner("Creating branch and staging files..."):
                    gh_tool.create_branch(repo_path, branch_name)
                    gh_tool.stage_files(repo_path, files_to_update)
                
                st.session_state.pr_step = "committing"
                st.rerun()

        # --- STEP 2: COMMIT ---
        elif st.session_state.pr_step == "committing":
            st.info("✅ Files successfully staged.")
            
            # Display Git Status
            st.markdown("**Current Git Status:**")
            st.code(gh_tool.get_git_status(repo_path), language="bash")
            
            st.warning("⚠️ Review the status above. Are you sure you want to commit?")
            if st.button("Commit Changes"):
                commit_msg = f"fix: resolved issue described in {issue_url}"
                with st.spinner("Committing..."):
                    gh_tool.commit_changes(repo_path, commit_msg)
                
                st.session_state.pr_step = "pushing"
                st.rerun()

        # --- STEP 3: PUSH & PR ---
        elif st.session_state.pr_step == "pushing":
            st.success("✅ Changes locally committed.")
            
            # Display Git Status
            st.markdown("**Current Git Status:**")
            st.code(gh_tool.get_git_status(repo_path), language="bash")
            
            if st.button("Push to Remote & Open Pull Request"):
                with st.spinner("Pushing branch and talking to GitHub API..."):
                    branch_name = st.session_state.branch_name
                    
                    # Push
                    push_output = gh_tool.push_branch(repo_path, branch_name)
                    
                    # Create PR
                    issue_id = issue_url.split('/')[-1]
                    pr_body = (
                        f"### Ghost Coder Autonomous Fix\n"
                        f"Closes {issue_url}\n\n"
                        f"**Test Verification Logs:**\n```\n{final_state.get('test_logs', 'Passed')}\n```"
                    )
                    pr_url = gh_tool.create_pull_request(
                        issue_url=issue_url,
                        branch_name=branch_name,
                        title=f"Ghost Coder Fix for issue #{issue_id}",
                        body=pr_body
                    )
                    
                if "http" in pr_url:
                    st.success(f"🎉 Pull Request Successfully Opened from branch `{branch_name}`")
                    st.markdown(f"**[View Pull Request on GitHub]({pr_url})**")
                    st.session_state.pr_step = "done"
                else:
                    st.error(f"Failed to open PR: {pr_url}")

        # --- DONE ---
        elif st.session_state.pr_step == "done":
            st.success("✨ Deployment Complete. Awaiting human code review on GitHub.")
            if st.button("Start New Fix"):
                # Clear session state to restart
                for key in ["final_state", "pr_step", "branch_name"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

with col2:
    st.markdown("### Agent Activity")
    # Check session state or local variable
    active_state = st.session_state.get("final_state") or (final_state if 'final_state' in locals() else None)
    
    if active_state:
        st.info(f"Attempts: {active_state.get('validation_attempts', 0)}")
        if active_state.get("test_logs"):
            with st.expander("Test Results"):
                st.code(active_state["test_logs"], language="bash")
    else:
        st.write("No active session.")
