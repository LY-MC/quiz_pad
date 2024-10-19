FROM python:3.9-alpine
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt  
COPY . .
RUN pip install gunicorn
CMD ["gunicorn", "-w", "1", "--threads", "1", "-b", "0.0.0.0:5003", "app:app"]

    