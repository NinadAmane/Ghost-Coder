import unittest
from unittest.mock import MagicMock, patch
from src.graph import create_ase_graph

class TestPRFlow(unittest.TestCase):
    @patch('src.graph.researcher_node')
    @patch('src.graph.coder_node')
    @patch('src.graph.tester_node')
    @patch('src.agents.submitter.GitHubTool')
    def test_pr_url_propagation_and_uniqueness(self, mock_gh_tool, mock_tester, mock_coder, mock_researcher):
        """
        Verify that when tester passes, the graph flows to submit_pr
        and updates the state with a PR URL, using a unique branch name.
        """
        # 1. Setup mocks
        mock_researcher.side_effect = lambda state: {**state, "files_to_modify": ["test.py"]}
        mock_coder.side_effect = lambda state: {**state, "updated_code": {"test.py": "print('fixed')"}}
        mock_tester.side_effect = lambda state: {**state, "test_passed": True}
        
        # Mock GitHubTool inside submitter
        mock_gh_instance = mock_gh_tool.return_value
        mock_gh_instance.create_pull_request.return_value = "https://github.com/test/repo/pull/123"
        
        # 2. Initialize graph
        graph = create_ase_graph()
        initial_state = {
            "issue_url": "https://github.com/test/repo/issues/1",
            "issue_description": "Fix bug",
            "repo_path": "workspace_clones/test_repo",
            "files_to_modify": [],
            "current_code": {},
            "updated_code": {},
            "error_history": [],
            "test_passed": False,
            "pr_url": ""
        }
        
        # 3. Run graph
        final_state = None
        for output in graph.stream(initial_state):
            for node_name, state_update in output.items():
                print(f"Finished node: {node_name}")
                final_state = state_update
        
        # 4. Assertions
        self.assertIsNotNone(final_state, "Final state should not be None")
        self.assertEqual(final_state["pr_url"], "https://github.com/test/repo/pull/123")
        
        # Verify unique branch name was used
        args, kwargs = mock_gh_instance.create_pull_request.call_args
        branch_name = kwargs.get('branch_name') or args[1]
        self.assertTrue(branch_name.startswith("ghost-coder-fix-"))
        self.assertTrue(len(branch_name) > len("ghost-coder-fix-"))
        print(f"Verified Branch Name: {branch_name}")
        print(f"Verified PR URL: {final_state['pr_url']}")

    @patch('src.graph.researcher_node')
    @patch('src.graph.coder_node')
    @patch('src.graph.tester_node')
    @patch('src.agents.submitter.GitHubTool')
    def test_pr_failure_reporting(self, mock_gh_tool, mock_tester, mock_coder, mock_researcher):
        """
        Verify that when PR submission fails, the error message is captured.
        """
        mock_researcher.side_effect = lambda state: {**state, "files_to_modify": ["test.py"]}
        mock_coder.side_effect = lambda state: {**state, "updated_code": {"test.py": "print('fixed')"}}
        mock_tester.side_effect = lambda state: {**state, "test_passed": True}
        
        mock_gh_instance = mock_gh_tool.return_value
        mock_gh_instance.create_pull_request.side_effect = Exception("Branch collision")
        
        graph = create_ase_graph()
        initial_state = {
            "issue_url": "https://github.com/test/repo/issues/1",
            "issue_description": "Fix bug",
            "repo_path": "workspace_clones/test_repo",
            "files_to_modify": [],
            "current_code": {},
            "updated_code": {},
            "error_history": [],
            "test_passed": False,
            "pr_url": ""
        }
        
        final_state = None
        for output in graph.stream(initial_state):
            for node_name, state_update in output.items():
                final_state = state_update
        
        self.assertTrue(final_state["pr_url"].startswith("Error:"))
        self.assertIn("Branch collision", final_state["pr_url"])
        print(f"Verified Error Capture: {final_state['pr_url']}")

if __name__ == "__main__":
    unittest.main()
