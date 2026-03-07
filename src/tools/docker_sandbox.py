import docker
import os
from typing import Dict, Any

class DockerSandbox:
    def __init__(self, image: str = "python:3.11-slim"):
        self.image = image
        self.client = docker.from_env()
        
    def run_tests(self, repo_dir: str, test_file_path: str, dependencies: list[str] = None) -> Dict[str, Any]:
        """
        Executes a test file inside an isolated Docker container.
        
        Args:
            repo_dir: The absolute path to the local repository code.
            test_file_path: The relative path to the test file inside the repo.
            dependencies: List of pip packages needed to run the tests.
            
        Returns:
            A dictionary containing 'success' boolean and 'logs' string.
        """
        abs_repo_dir = os.path.abspath(repo_dir)
        
        # Prepare the bash script to execute inside the container
        setup_deps = ""
        if dependencies:
            deps_str = " ".join(dependencies)
            setup_deps = f"pip install {deps_str} &&"
            
        # We ensure PYTHONPATH is set so local imports work
        command = f"bash -c '{setup_deps} export PYTHONPATH=/workspace && pytest {test_file_path}'"
        
        try:
            # We use auto_remove=False to capture logs, then remove manually
            container = self.client.containers.run(
                self.image,
                command=command,
                volumes={abs_repo_dir: {'bind': '/workspace', 'mode': 'rw'}},
                working_dir='/workspace',
                detach=True
            )
            
            result = container.wait(timeout=60) # Wait up to 60 seconds
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
