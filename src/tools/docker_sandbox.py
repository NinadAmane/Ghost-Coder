import docker
import os
import tarfile
import io

from src.logging_config import get_logger

logger = get_logger(__name__)


class DockerSandbox:
    """
    Runs test scripts inside isolated Docker containers.

    Raises on initialization if Docker is not available, so callers
    can catch and report clearly instead of failing mid-test.
    """

    DEFAULT_TIMEOUT_SECONDS = 120

    def __init__(self, image="python:3.11"):
        # Let docker.errors.DockerException propagate to caller
        # so tester_node can catch it and report clearly.
        self.client = docker.from_env()
        self.image = image

    def run_test(
        self,
        repo_path: str,
        test_script_content: str,
        test_file_name="test_fix.py",
        timeout: int | None = None,
    ) -> dict:
        """
        Runs a test script inside a Docker container using the repo as context.

        Args:
            repo_path: Local path to the cloned repository.
            test_script_content: Python source code of the test to run.
            test_file_name: Filename to write the test script as.
            timeout: Seconds to wait for the container to finish.
                     Defaults to DEFAULT_TIMEOUT_SECONDS.

        Returns:
            dict with 'exit_code' (int) and 'logs' (str).
        """
        if timeout is None:
            timeout = self.DEFAULT_TIMEOUT_SECONDS

        container = None
        try:
            # 1. Write the test script to the local repo path first
            test_file_path = os.path.join(repo_path, test_file_name)
            with open(test_file_path, 'w', encoding='utf-8') as f:
                f.write(test_script_content)

            # 2. Create container and start it with the repo path mounted
            # We intelligently install project dependencies so standard
            # packages (like pandas) are available
            setup_and_run_cmd = (
                "if [ -f pyproject.toml ] || [ -f setup.py ]; then "
                "pip install -e . || pip install . ; fi; "
                "if [ -f requirements.txt ]; then "
                "pip install -r requirements.txt; fi; "
                f"python {test_file_name}"
            )

            container = self.client.containers.run(
                self.image,
                command=["sh", "-c", setup_and_run_cmd],
                volumes={
                    os.path.abspath(repo_path): {
                        'bind': '/app',
                        'mode': 'rw'
                    }
                },
                working_dir='/app',
                detach=True
            )

            logger.info(
                "Docker container started, waiting up to %ds",
                timeout,
            )

            # 3. Wait for completion with timeout
            try:
                result = container.wait(timeout=timeout)
            except Exception as wait_err:
                # Covers requests.exceptions.ReadTimeout and
                # requests.exceptions.ConnectionError
                logger.error(
                    "Docker container timed out after %ds: %s",
                    timeout,
                    str(wait_err),
                )
                try:
                    container.kill()
                except Exception:
                    pass
                return {
                    "exit_code": 1,
                    "logs": (
                        f"Docker Sandbox Error: Container timed out "
                        f"after {timeout}s"
                    ),
                }

            logs = container.logs().decode('utf-8')
            exit_code = result.get('StatusCode', 1)

            logger.info(
                "Docker container finished with exit code %d", exit_code
            )

            return {
                "exit_code": exit_code,
                "logs": logs
            }

        except docker.errors.ImageNotFound:
            error_msg = f"Docker image '{self.image}' not found"
            logger.error(error_msg)
            return {"exit_code": 1, "logs": f"Docker Sandbox Error: {error_msg}"}

        except Exception as e:
            logger.error("Docker sandbox error: %s", str(e), exc_info=True)
            return {
                "exit_code": 1,
                "logs": f"Docker Sandbox Error: {str(e)}"
            }
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    logger.warning("Failed to remove Docker container")

            # Sandbox Cleanliness: Remove the local test file
            try:
                test_file_path = os.path.join(repo_path, test_file_name)
                if os.path.exists(test_file_path):
                    os.remove(test_file_path)
            except Exception:
                logger.warning("Failed to clean up test file")
