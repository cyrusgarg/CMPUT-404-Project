FROM python:3.12-alpine

# Sets the current working directory to be `/app`
WORKDIR /app

# Prevents Python from writing pyc and pycache files to disc
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt .
RUN pip install -r requirements.txt

COPY . .