#System
FROM python:3.8

#General requirements
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY nodes/testnode/requirements.txt .
RUN pip install -r requirements.txt

#Changes frequently
COPY . .
RUN pip install -e .
COPY nodes/testnode /app
WORKDIR /app

CMD ["uvicorn", "testnode:app", "--host", "0.0.0.0", "--port", "8000"]
