FROM python:3.11-slim

# Avoid writing .pyc files and enable unbuffered real-time log output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=7860

WORKDIR /app

# Install essential system build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition
COPY requirements.txt .

# Install dependencies using CPU-only PyTorch index explicitly
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download SentenceTransformer weights into image cache during build (instant cold-starts)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy repository source code
COPY . .

# Expose standard port
EXPOSE 7860

# Launch Uvicorn server bound to 0.0.0.0:7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
