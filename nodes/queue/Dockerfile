#System
FROM python:3.8

#General requirements
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY nodes/queue/requirements.txt .
RUN pip install -r requirements.txt

#Changes frequently
COPY rhnode rhnode
COPY setup.py .
COPY README.md .
RUN pip install -e . --no-deps
COPY nodes/queue /app
WORKDIR /app
#CMD ["python", "queue.py"]
CMD ["uvicorn", "newmanager:app", "--host", "0.0.0.0", "--port", "8000"]