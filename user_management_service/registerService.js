const Consul = require('consul');
const consul = new Consul({ host: 'consul', port: 8500 });

const serviceId = process.env.SERVICE_ID;
const serviceName = process.env.SERVICE_NAME;
const serviceAddress = process.env.SERVICE_ADDRESS;
const servicePort = parseInt(process.env.SERVICE_PORT, 10);

const registerService = () => {
  const details = {
    id: serviceId,
    name: serviceName,
    address: serviceAddress,
    port: servicePort,
  };

  consul.agent.service.register(details, (err) => {
    if (err) {
      console.error('Failed to register service:', err);
      setTimeout(registerService, 5000); // Retry after 5 seconds
    } else {
      console.log('Service registered successfully.');
    }
  });
};

registerService();