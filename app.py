import streamlit as st
import os
import time
from dotenv import load_dotenv
from src.graph import create_ase_graph
from src.tools.github_tools import GitHubTool

load_dotenv()

st.set_page_config(page_title="Ghost Coder ", layout="centered")

st.title("Ghost Coder")
st.markdown("A 4-node LangGraph pipeline that autonomously researches, codes, tests, and opens a PR for a GitHub Issue.")

# Sidebar for credentials
with st.sidebar:
    st.header("Credentials")
    github_token = st.text_input("GitHub Token", value=os.getenv("GITHUB_TOKEN", ""), type="password")
    groq_key = st.text_input("Groq API Key", value=os.getenv("GROQ_API_KEY", ""), type="password")
    
    if github_token:
        os.environ["GITHUB_TOKEN"] = github_token
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key

# Main Interface
issue_url = st.text_input("GitHub Issue URL", placeholder="https://github.com/owner/repo/issues/1")

if st.button("Start Orchestration", type="primary"):
    if not os.environ.get("GITHUB_TOKEN") or not os.environ.get("GROQ_API_KEY"):
        st.error("Please provide both GitHub and Groq API keys in the sidebar.")
        st.stop()
        
    if not issue_url:
        st.error("Please enter a valid GitHub Issue URL.")
        st.stop()

    with st.status("Initializing...", expanded=True) as status:
        st.write("Fetching issue details...")
        try:
            gh_tool = GitHubTool()
            issue_details = gh_tool.fetch_issue_details(issue_url)
            st.success(f"Found Issue: **{issue_details['title']}**")
        except Exception as e:
            status.update(label="Failed to fetch issue", state="error")
            st.error(str(e))
            st.stop()

        import shutil
        import stat
        def remove_readonly(func, path, excinfo):
            os.chmod(path, stat.S_IWRITE)
            func(path)
            
        workspace_dir = os.path.abspath("./workspace_clones/target_repo")
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir, onerror=remove_readonly)
        os.makedirs(workspace_dir, exist_ok=True)
        
        st.write("Cloning repository into isolated workspace...")
        if not gh_tool.clone_repository(issue_url, workspace_dir):
            status.update(label="Clone failed", state="error")
            st.error("Failed to clone repository. Check your token permissions.")
            st.stop()

        initial_state = {
            "issue_url": issue_url,
            "issue_description": f"{issue_details['title']}\\n\\n{issue_details['body']}",
            "repo_path": workspace_dir,
            "files_to_modify": [],
            "current_code": {},
            "updated_code": {},
            "error_history": [],
            "test_passed": False,
            "pr_url": ""
        }

        st.write("Building Graph...")
        graph = create_ase_graph()
        
        st.write("Starting Agent Loop...")
        status.update(label="Agents Running...")

    final_state = None
    
    # We create empty placeholders to dynamically render agent outputs
    st.markdown("### Agent Live Output")
    stream_container = st.container()
    
    try:
        for output in graph.stream(initial_state):
            for agent, state_update in output.items():
                with stream_container:
                    with st.expander(f"⚙️ Node Finished: **{agent.upper()}**", expanded=True):
                        if agent == "researcher":
                            st.write("**Files targeted for modification:**")
                            st.write(state_update.get('files_to_modify', []))
                            
                        elif agent == "coder":
                            st.write("**Code Fix Generated:**")
                            updated = state_update.get("updated_code", {})
                            for filepath, content in updated.items():
                                st.markdown(f"**`{filepath}`**")
                                st.code(content, language="python")
                                
                        elif agent == "tester":
                            passed = state_update.get("test_passed", False)
                            if passed:
                                st.success("✅ Sandbox Test Passed!")
                            else:
                                st.error("❌ Sandbox Test Failed! Sending logs back to Coder.")
                                if state_update.get("error_history"):
                                    st.code(state_update["error_history"][-1])
                                    
            final_state = state_update
            
    except Exception as e:
        import traceback
        st.error("Graph Execution Failed")
        st.code(traceback.format_exc())
        st.stop()

    if final_state and final_state.get("pr_url") and final_state["pr_url"].startswith("http"):
        st.success(f"🎉 **Success!** Pull Request autonomously opened: [View PR]({final_state['pr_url']})")
    else:
        st.error(f"Orchestration completed, but Pull Request failed: {final_state.get('pr_url', 'No details available')}")
