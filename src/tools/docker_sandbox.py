import docker
import os
import tarfile
import io

class DockerSandbox:
    def __init__(self, image="python:3.11-slim"):
        self.client = docker.from_env()
        self.image = image

    def run_test(self, repo_path: str, test_script_content: str, test_file_name="test_fix.py") -> dict:
        """
        Runs a test script inside a Docker container using the repo as context.
        """
        container = None
        try:
            # 1. Write the test script to the local repo path first
            test_file_path = os.path.join(repo_path, test_file_name)
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(test_script_content)

            # 2. Create container and start it with the repo path mounted
            # Note: We use volume mounting for simplicity since it's local
            container = self.client.containers.run(
                self.image,
                command=["python", test_file_name],
                volumes={
                    os.path.abspath(repo_path): {
                        'bind': '/app',
                        'mode': 'rw'
                    }
                },
                working_dir='/app',
                detach=True
            )

            # 3. Wait for completion and capture logs
            result = container.wait()
            logs = container.logs().decode('utf-8')
            
            exit_code = result.get('StatusCode', 1)
            
            return {
                "exit_code": exit_code,
                "logs": logs
            }

        except Exception as e:
            return {
                "exit_code": 1,
                "logs": f"Docker Sandbox Error: {str(e)}"
            }
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass
