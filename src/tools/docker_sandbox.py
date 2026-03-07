import docker
import os
from typing import Dict, Any

class DockerSandbox:
    def __init__(self):
        self.client = docker.from_env()
        
    def detect_language(self, repo_dir: str) -> Dict[str, str]:
        """Detects the primary language of the repository to select the Docker image."""
        if os.path.exists(os.path.join(repo_dir, "Cargo.toml")):
            return {"language": "rust", "image": "rust:latest", "default_cmd": "cargo test"}
        elif os.path.exists(os.path.join(repo_dir, "package.json")):
            return {"language": "node", "image": "node:18", "default_cmd": "npm test"}
        elif os.path.exists(os.path.join(repo_dir, "go.mod")):
            return {"language": "go", "image": "golang:latest", "default_cmd": "go test ./..."}
        else:
            # Default to Python
            return {"language": "python", "image": "python:3.11-slim", "default_cmd": "pytest"}
        
    def run_tests(self, repo_dir: str, test_file_path: str = "", dependencies: list[str] = None, custom_command: str = "") -> Dict[str, Any]:
        """
        Executes a test file inside an isolated Docker container based on the repo's language.
        
        Args:
            repo_dir: The absolute path to the local repository code.
            test_file_path: The relative path to the test file inside the repo.
            dependencies: List of packages needed to run the tests (mostly for Python now).
            custom_command: Overrides the default test execution command.
            
        Returns:
            A dictionary containing 'success' boolean and 'logs' string.
        """
        abs_repo_dir = os.path.abspath(repo_dir)
        lang_config = self.detect_language(abs_repo_dir)
        image = lang_config["image"]
        base_cmd = custom_command or lang_config["default_cmd"]
        
        # Build command depending on language
        if lang_config["language"] == "python":
            setup_deps = ""
            if dependencies:
                deps_str = " ".join(dependencies)
                setup_deps = f"pip install {deps_str} &&"
            cmd_target = f" {test_file_path}" if test_file_path else ""
            command = f"bash -c '{setup_deps} export PYTHONPATH=/workspace && {base_cmd}{cmd_target}'"
        else:
            # For Rust/Node, we typically run the default suite or the custom command directly
            command = f"bash -c '{base_cmd}'"
        
        try:
            # Use auto_remove=False to capture logs, then remove manually
            container = self.client.containers.run(
                image,
                command=command,
                volumes={abs_repo_dir: {'bind': '/workspace', 'mode': 'rw'}},
                working_dir='/workspace',
                detach=True
            )
            
            result = container.wait(timeout=120) # Given Rust compiles might take longer, increased to 120
            logs = container.logs().decode('utf-8')
            container.remove()
            
            return {
                "success": result["StatusCode"] == 0,
                "logs": logs
            }
            
        except docker.errors.ContainerError as e:
            return {
                "success": False,
                "logs": e.stderr.decode('utf-8') if e.stderr else str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "logs": f"Sandbox Error: {str(e)}"
            }
