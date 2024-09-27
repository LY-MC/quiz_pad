FROM python:3.9-alpine
WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install gunicorn
COPY . .
CMD ["gunicorn", "-w", "4", "--threads", "2", "-b", "0.0.0.0:5002", "app:app"]