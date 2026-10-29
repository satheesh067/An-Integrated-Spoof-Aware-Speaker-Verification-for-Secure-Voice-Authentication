FROM python:3.12-slim

# Install system audio dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python requirements
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

# Copy backend code, models, and data
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Start server with model warmup
CMD ["python", "scripts/run_project.py", "--warmup"]
