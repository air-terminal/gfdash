FROM python:3.13
ENV PYTHONUNBUFFERED 1
RUN mkdir /code
WORKDIR /code
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*
ADD requirements.txt /code/
RUN pip install -r requirements.txt
ADD . /code/
