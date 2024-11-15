const express = require('express');
const bodyParser = require('body-parser');
const winston = require('winston');
const LOGSTASH_HOST = process.env.LOGSTASH_HOST || "logstash";
const LOGSTASH_HTTP_PORT = process.env.LOGSTASH_HTTP_PORT || 6000;

const logger = winston.createLogger({
  transports: [
      new winston.transports.Console(),
      new winston.transports.Http({
          host: LOGSTASH_HOST,
          port: LOGSTASH_HTTP_PORT,
          level: 'info',
      })
  ],
});

function logMsg(msg) {
  logger.info(JSON.stringify({
      "service": "service_discovery",
      "msg": msg
  }));
}

class ServiceRegistry {
  constructor() {
    this.services = {};
  }

  registerService(name, ip, port) {
    const serviceKey = `${name}_${ip}:${port}`;
    this.services[serviceKey] = {
      name,
      ip,
      port,
      timestamp: Date.now(),
    };
    console.log(`Registered service: ${name} at ${ip}:${port}`);
    logMsg(`Registered service: ${name} at ${ip}:${port}`);
  }

  unregisterService(serviceKey) {
    if (this.services[serviceKey]) {
      console.log(`Unregistering service: ${serviceKey}`);
      logMsg(`Unregistering service: ${serviceKey}`);
      delete this.services[serviceKey];
    }
  }

  getAllServices() {
    return Object.values(this.services);
  }

  // async pingServices() {
  //   for (const key in this.services) {
  //     const service = this.services[key];
  //     const serviceUrl = `http://${service.name}:${service.port}/api/v1/health`;

  //     try {
  //       const response = await axios.get(serviceUrl);
  //       if (response.status === 200 && response.data.status === 'healthy') {
  //         // Update the timestamp to indicate service is still healthy
  //         this.services[key].timestamp = Date.now();
  //         console.log(`Service ${service.name} is healthy.`);
  //       } else {
  //         // Unregister the service if not healthy
  //         console.log(`Service ${service.name} is not healthy.`);
  //         this.unregisterService(key);
  //       }
  //     } catch (error) {
  //       console.error(`Failed to reach service ${service.name} at ${serviceUrl}: ${error.message}`);
  //       this.unregisterService(key);
  //     }
  //   }
  // }
}

const registry = new ServiceRegistry();
const app = express();
app.use(bodyParser.json());

app.post('/register', (req, res) => {
  const { name, ip, port } = req.body;
  if (name && ip && port) {
    registry.registerService(name, ip, port);
    res.status(200).send('Service registered successfully');
    logMsg(`Service registered successfully: ${name} at ${ip}:${port}`);
  } else {
    res.status(400).send('Invalid request data');
    logMsg('Invalid request data for service registration');
  }
});

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'UP' });
  logMsg('Health check endpoint called');
});

app.get('/services', (req, res) => {
  res.json(registry.getAllServices());
  logMsg('Retrieved all registered services');
});

app.get('/status', (req, res) => {
  res.status(200).json({
    status: 'Service discovery is up and running',
  });
  logMsg('Status endpoint called');
});

const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Service Discovery running on port ${PORT}`);
  logMsg(`Service Discovery running on port ${PORT}`);
});