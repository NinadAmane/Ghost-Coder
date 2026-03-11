import docker
import os
import tarfile
import io

class DockerSandbox:
    def __init__(self):
        self.client = None

    def run_tests(self, repo_dir: str, test_file_path: str) -> dict:
        """
        Spins up a Python Docker container, mounts the code, runs the test script,
        and returns the exit code and logs.
        """
        try:
            import docker
            self.client = docker.from_env()
        except Exception as e:
            return {
                "exit_code": -1,
                "logs": f"SYSTEM ERROR: Docker daemon is not running. Please start Docker Desktop on your machine! Details: {str(e)}",
                "success": False
            }
            
        container = None
        try:
            # We use a lightweight python image
            image = "python:3.11-slim"
            
            # Ensure the image is pulled
            try:
                self.client.images.get(image)
            except docker.errors.ImageNotFound:
                print(f"Pulling image {image}...")
                self.client.images.pull(image)

            # Spin up container
            container = self.client.containers.run(
                image,
                command="tail -f /dev/null", # Keep alive
                detach=True,
                working_dir="/workspace"
            )

            # Copy files to container
            self._copy_to_container(container, repo_dir, "/workspace")

            # Execute the test
            # test_file_path should be relative to repo_dir (e.g. "test_fix.py")
            cmd = f"python {test_file_path}"
            
            exit_code, output = container.exec_run(cmd)
            
            logs = output.decode('utf-8')
            
            return {
                "exit_code": exit_code,
                "logs": logs,
                "success": exit_code == 0
            }

        except Exception as e:
            return {
                "exit_code": -1,
                "logs": str(e),
                "success": False
            }
        finally:
            if container:
                container.stop()
                container.remove()

    def _copy_to_container(self, container, src_path: str, dest_path: str):
        """
        Helper to copy an entire directory into a docker container
        """
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            # Add the directory contents but strip the top level folder from the archive path
            tar.add(src_path, arcname='.')
        
        tar_stream.seek(0)
        container.put_archive(path=dest_path, data=tar_stream)
