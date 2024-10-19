FROM python:3.9-alpine

# Install Node.js and npm
RUN apk add --no-cache nodejs npm

WORKDIR /usr/src/app

# Copy package.json and install dependencies
COPY package.json ./
RUN npm install

COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY . .
RUN pip install gunicorn

# Ensure the service registration script is executable
RUN chmod +x registerService.js

CMD ["sh", "-c", "node registerService.js & gunicorn -w 4 --threads 2 -b 0.0.0.0:5002 app:app"]