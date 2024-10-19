const axios = require('axios');

const serviceId = process.env.SERVICE_ID || 'game_engine_service';
const serviceName = process.env.SERVICE_NAME || 'game_engine_service';
const serviceAddress = process.env.SERVICE_ADDRESS || 'game_engine_service';  
const servicePort = parseInt(process.env.SERVICE_PORT, 10) || 5003;

const registerService = async () => {
  try {
    const response = await axios.post('http://service_discovery:3000/register', {
      name: serviceName,
      ip: serviceAddress,
      port: servicePort,
    });
    console.log('Service registered successfully:', response.data);
  } catch (err) {
    console.error('Failed to register service:', err);
    setTimeout(registerService, 5000); // Retry after 5 seconds
  }
};

registerService();