#System
FROM pytorch/pytorch:1.13.1-cuda11.6-cudnn8-runtime
# FROM python:3.8 #If GPU is not necessary
RUN apt-get update -y
RUN apt-get install git -y

#General requirements
RUN pip install git+https://github.com/CAAI/rh-node.git

#Unique to project requirements
COPY requirements.txt /app/requirements.txt
COPY mydependent.py /app/mydependent.py
RUN pip install -r /app/requirements.txt
WORKDIR /app

## Command to start the server
CMD ["uvicorn", "mydependent:app", "--host", "0.0.0.0", "--port", "8000"]