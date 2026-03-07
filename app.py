import streamlit as st
import os
from dotenv import load_dotenv
from src.graph import create_ase_graph
from src.tools.github_tools import GitHubIntegration

load_dotenv()

st.set_page_config(page_title="Ghost Coder Orchestrator", layout="wide")

st.title("Ghost Coder: Multi-Agent Orchestrator for Git Issues")
st.markdown("This system utilizes LangGraph and Groq's APIs to dynamically pull GitHub issues and route them through virtual *Researcher*, *Coder*, and *QA* agents.")

st.sidebar.header("Configuration")
github_token = st.sidebar.text_input("GitHub Token", value=os.getenv("GITHUB_TOKEN", ""), type="password")
groq_key = st.sidebar.text_input("Groq API Key", value=os.getenv("GROQ_API_KEY", ""), type="password")

if github_token:
    os.environ["GITHUB_TOKEN"] = github_token
if groq_key:
    os.environ["GROQ_API_KEY"] = groq_key

repo_name = st.text_input("Repository (e.g., owner/repo)", "langchain-ai/langchain")
issue_number = st.number_input("Issue Number", min_value=1, value=1234, step=1)

if st.button("Start Orchestration"):
    if not github_token or not groq_key:
        st.error("Please configure your API keys in the sidebar.")
    else:
        with st.status("Initializing Ghost Coder...", expanded=True) as status:
            st.write("Fetching issue details from GitHub...")
            github_client = GitHubIntegration()
            
            try:
                issue_data = github_client.get_issue_details(repo_name, issue_number)
                st.write(f"**Issue Title:** {issue_data['title']}")
            except Exception as e:
                st.error(f"Failed to fetch issue: {e}")
                st.stop()
                
            st.write(f"Cloning repository `{repo_name}` into local workspace...")
            workspace_dir = os.path.abspath(f"./.workspace/{repo_name.replace('/', '_')}")
            clone_url = f"https://github.com/{repo_name}.git"
            
            if not github_client.clone_repository(clone_url, workspace_dir):
                st.error("Failed to clone repository.")
                st.stop()
                
            st.write("Initializing LangGraph orchestrator...")
            graph = create_ase_graph()
            
            initial_state = {
                "github_issue_url": issue_data["url"],
                "issue_description": f"{issue_data['title']}\n\n{issue_data['body']}",
                "repo_path": workspace_dir,
                "validation_attempts": 0
            }
            
            st.write("Entering Multi-Agent Graph...")
            
            final_state = None
            for event in graph.stream(initial_state):
                for node_name, node_state in event.items():
                    with st.expander(f"⚙️ **{node_name.capitalize()} Agent** finished a step.", expanded=True):
                        if node_name == "researcher":
                            st.markdown("**🔍 Researcher Output:**")
                            st.markdown(node_state.get("research_summary", ""))
                        elif node_name == "coder":
                            st.markdown("**💻 Coder Drafted Fix:**")
                            st.code(node_state.get("code_fix", ""), language="python")
                        elif node_name == "qa":
                            st.markdown("**🧪 QA Results:**")
                            if node_state.get("test_passed"):
                                st.success("Test Passed!")
                            else:
                                st.error("Test Failed. Sending feedback to Coder...")
                            st.code(node_state.get("test_logs", ""), language="bash")
                            
                    final_state = node_state
                    
            status.update(label="Orchestration Complete!", state="complete", expanded=False)
            
        if final_state:
            st.subheader("Agent Outputs")
            
            tab1, tab2, tab3 = st.tabs(["Researcher Report", "Coder Fix", "QA Results"])
            
            with tab1:
                st.markdown(final_state.get("research_summary", "No report generated."))
                
            with tab2:
                st.code(final_state.get("code_fix", "No fix generated."), language="python")
                
            with tab3:
                if final_state.get("test_passed"):
                    st.success("✅ All tests passed in Docker Sandbox.")
                    st.markdown("---")
                    st.subheader("🚢 Ready for Deployment")
                    st.write("The QA agent has verified the fix. You can now submit this automated fix back to the repository.")
                    
                    pr_title = st.text_input("PR Title", value=f"Fix for Issue #{issue_number}")
                    pr_branch = st.text_input("Branch Name", value=f"ghost-coder/fix-issue-{issue_number}")
                    
                    if st.button("Submit Pull Request"):
                        with st.spinner("Pushing code and Creating Pull Request on GitHub..."):
                            
                            push_success = github_client.commit_and_push_changes(
                                repo_dir=workspace_dir,
                                branch_name=pr_branch,
                                commit_message=pr_title
                            )
                            
                            if not push_success:
                                st.error("Failed to push local changes to GitHub branch.")
                            else:
                                pr_url = github_client.create_pull_request(
                                    repo_name=repo_name,
                                    branch_name=pr_branch,
                                    title=pr_title,
                                    body=f"Automated fix generated by Ghost Coder for issue #{issue_number}.\n\n"
                                )
                                if pr_url.startswith("http"):
                                    st.success(f"Pull Request successfully created! [View PR here]({pr_url})")
                                    st.balloons()
                                else:
                                    st.error(pr_url)

                else:
                    st.error(f"❌ Tests failed after {final_state.get('validation_attempts')} attempts.")
                
                if final_state.get("test_logs"):
                    st.subheader("Test Execution Logs")
                    st.code(final_state.get("test_logs"), language="bash")
                    
        if not final_state.get("test_passed"):
            st.snow()
