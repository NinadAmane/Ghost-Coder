# Use a lightweight python image
FROM python:3.11-slim

# Install git and docker CLI
RUN apt-get update && apt-get install -y git docker.io && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install dependencies
COPY pyproject.toml README.md ./

# Use pip to install the project
RUN pip install .[dev]

# Copy the source code
COPY . .

# Set the default command to run the orchestrator
ENTRYPOINT ["python", "-m", "src.main"]
