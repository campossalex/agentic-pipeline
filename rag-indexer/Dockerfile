FROM python:3.12-slim
RUN pip install --no-cache-dir "pymilvus>=2.6,<3"
COPY index.py /index.py
ENTRYPOINT ["python", "/index.py"]
