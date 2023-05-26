#System
FROM python:3.8

#General requirements
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY tests/nodes/testnode_add/requirements.txt .
RUN pip install -r requirements.txt

#Changes frequently
COPY rhnode rhnode
COPY setup.py .
COPY README.md .
RUN pip install -e . --no-deps
COPY tests/nodes/testnode_add /app
WORKDIR /app

CMD ["uvicorn", "add:app", "--host", "0.0.0.0", "--port", "8000"]
