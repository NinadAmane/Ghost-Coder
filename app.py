import streamlit as st
import os
from dotenv import load_dotenv
from src.graph import create_ase_graph
from src.tools.github_tools import GitHubIntegration

load_dotenv()

st.set_page_config(page_title="Ghost Coder", layout="wide")

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
                
                if issue_data.get("state", "open").lower() == "closed":
                    st.warning(f"⚠️ **Notice:** Issue #{issue_number} has already been marked as closed/solved on GitHub. Please try a different issue.")
                    status.update(label="Orchestration Stopped", state="error", expanded=True)
                    st.stop()
                    
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
            try:
                for event in graph.stream(initial_state):
                    for node_name, node_state in event.items():
                        with st.expander(f"⚙️ **{node_name.capitalize()} Agent** finished a step.", expanded=True):
                            if node_name == "researcher":
                                st.markdown("**🔍 Researcher Output:**")
                                st.markdown(node_state.get("research_summary", ""))
                            elif node_name == "coder":
                                st.markdown("**💻 Coder Drafted Fix:**")
                                code_fix_text = node_state.get("code_fix", "")
                                if "```json" in code_fix_text:
                                    explanation = code_fix_text.split("```json")[0]
                                    if explanation.strip():
                                        st.markdown(explanation)
                                
                                modified_files = node_state.get("modified_files_content", {})
                                for file_path, content in modified_files.items():
                                    with st.expander(f"Modified: {file_path}", expanded=True):
                                        st.code(content, language="python")

                            elif node_name == "qa":
                                st.markdown("**🧪 QA Results:**")
                                if node_state.get("test_passed"):
                                    st.success("Test Passed!")
                                else:
                                    st.error("Test Failed. Sending feedback to Coder...")
                                
                                if node_state.get("qa_reflection"):
                                    st.markdown(node_state.get("qa_reflection"))
                                    
                                if node_state.get("test_logs"):
                                    with st.expander("View Raw Test Logs"):
                                        st.code(node_state.get("test_logs", ""), language="bash")
                                
                        final_state = node_state
            except Exception as e:
                import groq
                import re
                if isinstance(e, groq.RateLimitError):
                    # Try to extract the retry time from the message
                    match = re.search(r"try again in ([\d\.]+[ms]|\d+:\d+)", str(e))
                    retry_time = match.group(1) if match else "a few minutes"
                    st.warning(f"⏳ **Groq API Rate Limit Reached.** Please wait {retry_time} before trying again. The free tier allows limited tokens per day.")
                else:
                    st.error(f"An unexpected error occurred: {str(e)}")
                status.update(label="Orchestration Stopped", state="error", expanded=True)
                st.stop()
                    
            status.update(label="Orchestration Complete!", state="complete", expanded=False)
            
            # Store in session state to persist across UI reruns
            st.session_state.final_state = final_state
            st.session_state.workspace_dir = workspace_dir
            
if st.session_state.get("final_state"):
    final_state = st.session_state.final_state
    workspace_dir = st.session_state.workspace_dir
    st.subheader("Agent Outputs")
    
    tab1, tab2, tab3 = st.tabs(["Researcher Report", "Coder Fix", "QA Results"])
    
    with tab1:
        st.markdown(final_state.get("research_summary", "No report generated."))
        
    with tab2:
        code_fix_text = final_state.get("code_fix", "No fix generated.")
        if "```json" in code_fix_text:
            explanation = code_fix_text.split("```json")[0]
            if explanation.strip():
                st.markdown(explanation)
        elif code_fix_text != "No fix generated.":
            st.markdown(code_fix_text)
            
        modified_files = final_state.get("modified_files_content", {})
        if not modified_files and code_fix_text == "No fix generated.":
            st.write("No fix generated.")
        else:
            for file_path, content in modified_files.items():
                with st.expander(f"File: {file_path}", expanded=True):
                    st.code(content, language="python")
        
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
                    github_client = GitHubIntegration()
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
        
        if final_state.get("qa_reflection"):
            st.markdown(final_state.get("qa_reflection"))
            
        if final_state.get("test_logs"):
            st.subheader("Test Execution Logs")
            with st.expander("View Raw Test Logs"):
                st.code(final_state.get("test_logs"), language="bash")
