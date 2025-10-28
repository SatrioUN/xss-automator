FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
# If you need Playwright in Docker uncomment the next line:
# RUN playwright install --with-deps
CMD ["python", "main.py", "--config", "config.yaml"]
