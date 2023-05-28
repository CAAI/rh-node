#System
FROM python:3.8

#Changes frequently
COPY rhnode rhnode
COPY setup.py .
COPY README.md .
RUN pip install -e .
COPY nodes/manager /app
WORKDIR /app

CMD ["uvicorn", "manager:app", "--host", "0.0.0.0", "--port", "8000"]