FROM python:3.12-slim

WORKDIR /app

# Build deps for faiss / onnxruntime wheels are prebuilt; git is not needed.
# The ONNX model + tokenizer ship inside app/onnx_model/ (bundled in the
# repo), so no model download happens at build or runtime.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1

# $PORT is provided by the host (Fly.io / Render). Default 8000 for local runs.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
