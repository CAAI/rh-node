#System
FROM python:3.8

#General requirements
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY nodes/queue/requirements.txt .
RUN pip install -r requirements.txt

#Changes frequently
COPY . . 
RUN pip install -e .
COPY nodes/queue /app
WORKDIR /app
CMD ["uvicorn", "queue:app", "--host", "0.0.0.0", "--port", "8000"]