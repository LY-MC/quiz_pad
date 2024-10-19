const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');

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
  }

  unregisterService(serviceKey) {
    if (this.services[serviceKey]) {
      console.log(`Unregistering service: ${serviceKey}`);
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
  } else {
    res.status(400).send('Invalid request data');
  }
});

// Health check endpoint for the service discovery server itself
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'UP' });
});

// Endpoint to see all registered services
app.get('/services', (req, res) => {
  res.json(registry.getAllServices());
});

app.get('/status', (req, res) => {
  res.status(200).json({
    status: 'Service discovery is up and running',
  });
});

// // Clean up old services and ping registered services periodically
// setInterval(() => {
//   registry.pingServices();
// }, 60 * 1000); // Ping services every 1 minute

// Start the service discovery server
const PORT = 3000;
app.listen(PORT, () => {
  console.log(`Service Discovery running on port ${PORT}`);
  // Optionally, you can call a function here to notify another service on start
});