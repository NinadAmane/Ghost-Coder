import streamlit as st
import os
import time
import hashlib
from src.graph import create_ase_graph
from src.tools.github_tools import GitHubTool
from src.metrics import RunMetrics
from dotenv import load_dotenv

# Load local .env (ignored if deployed on Streamlit Cloud)
load_dotenv(override=True)

st.set_page_config(
    page_title="Ghost Coder | Autonomous Agent",
    page_icon="",
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
    .metric-card {
        padding: 1rem;
        border-radius: 8px;
        background: rgba(75, 0, 130, 0.15);
        border: 1px solid rgba(147, 112, 219, 0.3);
        margin-bottom: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar Configuration ---
with st.sidebar:
    st.image("Ghost_coder_logo.png", width=500)
    st.title("Settings")
    
    st.markdown("### Authentication")
    app_password = st.text_input("App Password", type="password", help="Enter the password to use this app.")
    
    # Load keys from Streamlit Secrets or .env
    gh_token = ""
    groq_key = ""
    expected_password = "demo" # Fallback password if not set
    
    try:
        gh_token = st.secrets.get("GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN", "")
        groq_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "")
        expected_password = st.secrets.get("APP_PASSWORD") or os.getenv("APP_PASSWORD", "demo")
    except Exception:
        gh_token = os.getenv("GITHUB_TOKEN", "")
        groq_key = os.getenv("GROQ_API_KEY", "")
        expected_password = os.getenv("APP_PASSWORD", "demo")

    # --- Cost estimation config ---
    st.markdown("### Cost Estimation")
    cost_per_million = st.number_input(
        "Cost per 1M tokens (USD)",
        min_value=0.0,
        value=0.0,
        step=0.01,
        help="Set to 0 to disable cost estimation. "
             "Groq free tier = $0. Paid tiers vary by model.",
    )


# --- Main UI ---
logo_col, title_col = st.columns([1, 15]) # Adjust the ratio [1, 10] to change spacing

with title_col:
    st.title("Ghost Coder")
with logo_col:
    # Assuming you are using the same logo from the sidebar
    st.image("Ghost_coder_logo-transparent-only-logo.png", width=70) 

st.markdown("""
Welcome to **Ghost Coder**, an experimental multi-agent system that attempts to autonomously resolve GitHub issues.
It runs generated patches through an isolated Docker sandbox to check correctness before proposing a Pull Request for human review.

**How to use:**
1. 🔗 **Input Target:** Paste a valid GitHub Issue URL into the field below.
2. 🔑 **Authenticate:** Ensure your GitHub and Groq API Keys are set in the sidebar.
3. ⚡ **Execute:** Click "Execute Autonomous Fix" to trigger the `Researcher ➡️ Coder ➡️ Tester` pipeline.
4. 🚀 **Deploy:** Once the agents verify the fix, use the Human-in-the-Loop pipeline to review and push your Pull Request.
""")
st.divider()

col1, col2 = st.columns([2, 1])

with col1:
    issue_url = st.text_input("Issue URL", placeholder="https://github.com/owner/repo/issues/123")
    
    if st.button("Execute Autonomous Fix"):
        if app_password != expected_password:
            st.error("Incorrect password.")
        elif not issue_url:
            st.warning("Please provide a GitHub Issue URL.")
        elif not gh_token or not groq_key:
            st.error("Missing API keys in Streamlit secrets or .env file.")
        else:
            gh_tool = GitHubTool(token=gh_token)
            
            with st.status("Initializing Environment...", expanded=True) as status:
                st.write("🔍 Fetching issue metadata...")
                issue_info = gh_tool.fetch_issue_details(issue_url)
                
                if "Error" in issue_info['title']:
                    st.error(f"Failed to fetch issue: {issue_info['body']}")
                    st.stop()
                
                st.write(f"**Targeting:** {issue_info['title']}")
                
                session_id = hashlib.md5(issue_url.encode()).hexdigest()[:8]
                workspace_dir = os.path.abspath(f"./workspace_clones/target_repo_{session_id}")
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
                    "github_token": gh_token,
                    "groq_api_key": groq_key,
                    "files_to_modify": [],
                    "research_summary": "",
                    "updated_code": {},
                    "test_logs": "",
                    "test_passed": False,
                    "test_explanation": "",
                    "validation_attempts": 0
                }
                
                # Fresh metrics instance per orchestration call — scoped to
                # this run, stored in session_state, zero cross-session leakage.
                run_metrics = RunMetrics()
                run_metrics.start_run()

                graph = create_ase_graph(metrics=run_metrics)
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
                
                success = bool(final_state and final_state.get("test_passed"))
                run_metrics.end_run(success=success)

                if success:
                    status.update(label="✅ Success! Issue Fixed.", state="complete")
                    st.success("Issue resolved and verified by automated tests!")
                    st.balloons()
                    
                    # Persist state for PR pipeline
                    st.session_state.final_state = final_state
                    if "pr_step" not in st.session_state:
                        st.session_state.pr_step = "branching"
                else:
                    status.update(label="❌ Failed after multiple attempts.", state="error")

                # Store metrics in session state (scoped per-session, per-run)
                st.session_state.run_metrics = run_metrics.to_dict()

    # --- HUMAN-IN-THE-LOOP DEPLOYMENT PIPELINE ---
    if st.session_state.get("final_state") and st.session_state.final_state.get("test_passed"):
        st.divider()
        st.header("🚀 Deployment Pipeline (Human-in-the-Loop)")
        
        final_state = st.session_state.final_state
        gh_tool = GitHubTool(token=final_state["github_token"])
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
                for key in ["final_state", "pr_step", "branch_name", "run_metrics"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

with col2:
    st.markdown("### 📊 Run Metrics")

    metrics_data = st.session_state.get("run_metrics")
    active_state = st.session_state.get("final_state") or (
        final_state if 'final_state' in locals() else None
    )

    if metrics_data:
        # --- Overall status ---
        if metrics_data["final_success"]:
            st.success("✅ Run Succeeded")
        else:
            st.error("❌ Run Failed")

        # --- Key numbers ---
        m1, m2 = st.columns(2)
        with m1:
            st.metric(
                "Total Duration",
                f"{metrics_data['run_duration_ms'] / 1000:.1f}s",
            )
        with m2:
            st.metric(
                "Validation Attempts",
                metrics_data["total_validation_attempts"],
            )

        m3, m4 = st.columns(2)
        with m3:
            st.metric("Total Tokens", f"{metrics_data['total_tokens']:,}")
        with m4:
            if cost_per_million > 0:
                est_cost = (
                    metrics_data["total_tokens"] / 1_000_000
                ) * cost_per_million
                st.metric("Est. Cost", f"${est_cost:.4f}")
            else:
                st.metric("Est. Cost", "N/A")

        # --- Per-node breakdown ---
        st.markdown("#### Per-Node Latency")
        for node_name, node_data in metrics_data.get("nodes", {}).items():
            icon = (
                "📁" if node_name == "researcher"
                else "💻" if node_name == "coder"
                else "🧪"
            )
            status_icon = "✅" if node_data["all_succeeded"] else "❌"
            st.markdown(
                f"**{icon} {node_name.capitalize()}** {status_icon}  \n"
                f"Executions: {node_data['executions']} · "
                f"Avg: {node_data['avg_duration_ms'] / 1000:.1f}s · "
                f"Total: {node_data['total_duration_ms'] / 1000:.1f}s"
            )
            if node_data["errors"]:
                with st.expander(f"{node_name} errors"):
                    for err in node_data["errors"]:
                        st.warning(err)

        # --- Test logs ---
        if active_state and active_state.get("test_logs"):
            with st.expander("Test Logs"):
                st.code(active_state["test_logs"], language="bash")

    elif active_state:
        # Fallback for runs that happened before metrics were added
        st.info(f"Attempts: {active_state.get('validation_attempts', 0)}")
        if active_state.get("test_logs"):
            with st.expander("Test Results"):
                st.code(active_state["test_logs"], language="bash")
    else:
        st.write("No active session.")
