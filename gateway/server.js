const Redis = require("ioredis");
const express = require("express");
const axios = require("axios");
const winston = require('winston');
const rateLimit = require("express-rate-limit");
let serviceIndexes = {};

const app = express();
app.use(express.json());
const PORT = process.env.PORT || 5000;

const MAX_RETRIES = process.env.MAX_RETRIES || 3;
const MAX_REDIRECTS = process.env.MAX_REDIRECTS || 3;

const LOGSTASH_HOST = process.env.LOGSTASH_HOST || "logstash";
const LOGSTASH_HTTP_PORT = process.env.LOGSTASH_HTTP_PORT || 6000;

const { SagaCoordinator, createUserStep, deleteUserStep, createGameSessionStep, deleteGameSessionStep } = require('./saga_coordinator');


const logWithFixedLabelWidth = (label, message, width = 25) => {
  const paddedLabel = label.padEnd(width, ' ');
  console.log(`${paddedLabel}| ${message}`);
};

const errorWithFixedLabelWidth = (label, error1, error2, width = 25) => {
  const paddedLabel = label.padEnd(width, ' ');
  console.error(`${paddedLabel}|`, error1, error2);
};

const redisClient = new Redis.Cluster([
  { port: 6379, host: 'redis-node-1' },
  { port: 6380, host: 'redis-node-2' },
  { port: 6381, host: 'redis-node-3' },
  { port: 6382, host: 'redis-node-4' },
  { port: 6383, host: 'redis-node-5' },
  { port: 6384, host: 'redis-node-6' }
]);

redisClient.on("connect", () => {
  console.log("Connected to Redis cluster");
});

redisClient.on("error", (err) => {
  console.error("Redis connection error:", err);
  logMsg(`Redis connection error: ${err.message}`);
});

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
        "service": "gateway",
        "msg": msg
    }));
}

app.post('/users/create_with_game', async (req, res) => {
  const userData = req.body.user;
  const gameData = {};

  if (!userData) {
      return res.status(400).json({ error: "Invalid request data" });
  }

  const saga = new SagaCoordinator();
  saga.addStep(createUserStep(userData), deleteUserStep(userData));
  saga.addStep(createGameSessionStep(gameData), deleteGameSessionStep(gameData));

  try {
      await saga.execute();
      res.status(201).json({ message: "User and game session created successfully", user_id: userData._id, game_id: gameData._id });
  } catch (e) {
      res.status(500).json({ error: "Failed to create user and game session" });
  }
});

const cacheSetValue = async (key, value, timeout = null) => {
  try {
    if (timeout) {
      await redisClient.set(key, value, 'EX', timeout);
    } else {
      await redisClient.set(key, value);
    }
    logWithFixedLabelWidth("cacheSetValue", `Successfully set ${key} to ${value}`);
    logMsg(`Successfully set ${key} to ${value}`);
  } catch (err) {
    errorWithFixedLabelWidth("cacheSetValue", 'Error setting value:', err);
    logMsg(`Error setting value for ${key}: ${err.message}`);
  }
};

const cacheGetValue = async (key) => {
  try {
    const value = await redisClient.get(key);
    if (value) {
      logWithFixedLabelWidth("cacheGetValue", `Value for ${key}: ${value}`);
      logMsg(`Value for ${key}: ${value}`);
      return value;
    } else {
      logWithFixedLabelWidth("cacheGetValue", `No value found for ${key}`);
      logMsg(`No value found for ${key}`);
      return null;
    }
  } catch (err) {
    errorWithFixedLabelWidth("cacheGetValue", 'Error getting value:', err.message);
    logMsg(`Error getting value for ${key}: ${err.message}`);
    return null;
  }
};

const cacheMiddleware = async (req, res, next) => {
  if (req.method !== "GET") {
    return next();
  }

  const cacheKey = req.originalUrl;
  logWithFixedLabelWidth("cacheMiddleware", `Checking cache for: ${cacheKey}`);
  logMsg(`Checking cache for: ${cacheKey}`);

  const maxRetries = 5;
  let retries = 0;

  while (retries < maxRetries) {
    try {
      const cachedData = await cacheGetValue(cacheKey);

      if (cachedData) {
        logWithFixedLabelWidth("cacheMiddleware", `Serving from cache for: ${cacheKey}`);
        logMsg(`Serving from cache for: ${cacheKey}`);
        return res.status(200).json(JSON.parse(cachedData));
      } else {
        logWithFixedLabelWidth("cacheMiddleware", `Cache miss for: ${cacheKey}`);
        logMsg(`Cache miss for: ${cacheKey}`);
        break;
      }
    } catch (err) {
      retries++;
      errorWithFixedLabelWidth("cacheMiddleware", `Cache error (attempt ${retries}):`, err.message);
      logMsg(`Cache error for ${cacheKey} (attempt ${retries}): ${err.message}`);
      if (retries >= maxRetries) {
        logWithFixedLabelWidth("cacheMiddleware", `Max retries reached for: ${cacheKey}`);
        logMsg(`Max retries reached for: ${cacheKey}`);
        break;
      }
    }
  }

  const serviceName = req.originalUrl.startsWith('/users') ? 'user_management_service' : 'game_engine_service';

  try {
    const response = await redirectRequest(serviceName, req.method, req.originalUrl, req.body, req.headers);
    res.json(response.data);
  } catch (err) {
    errorWithFixedLabelWidth("serviceRoute", "Request failed:", err.message);
    logMsg(`Request to ${serviceName} failed: ${err.message}`);
    if (err.message.includes(`No available ${serviceName} instances`)) {
      res.status(503).json({ message: `${serviceName.replace('_', ' ')} is currently unavailable. Please try again later.` });
    } else {
      res.status(503).json({ message: `Unable to process the request`, last_error: err.message });
    }
  }
};

const shouldCache = (endpoint, responseCode) => {
  return (
    (endpoint === '/users/status' || endpoint === "/game/questions") &&
    responseCode === 200
  );
};

const limiter = rateLimit({
  windowMs: 5 * 60 * 1000,
  max: 15,
  message: "Too many requests, please try again later.",
});

app.use(limiter);

const getNextServiceInstance = async (serviceName, instances) => {
  if (!serviceIndexes[serviceName]) {
    serviceIndexes[serviceName] = 0;
  }

  let serviceInstance = null;
  let instanceIndex = serviceIndexes[serviceName];
  let checkedInstances = new Set();

  while (serviceInstance === null && checkedInstances.size < instances.length) {
    const currentInstance = instances[instanceIndex];

    checkedInstances.add(currentInstance.ip);
    
    const circuitStatus = await cacheGetValue(`circuit:${currentInstance.ip}`);
      
    if (circuitStatus !== '0') {
      serviceInstance = currentInstance;
    } else {
      logWithFixedLabelWidth("getNextServiceInstance", `Circuit for ${currentInstance.ip} is open. Skipping`);
      logMsg(`Circuit for ${currentInstance.ip} is open. Skipping`);
    }
    
    instanceIndex = (instanceIndex + 1) % instances.length;
  }

  serviceIndexes[serviceName] = instanceIndex;

  if (serviceInstance === null) {
    logWithFixedLabelWidth("getNextServiceInstance", `No available instances for ${serviceName} (all circuits are open)`);
    logMsg(`No available instances for ${serviceName} (all circuits are open)`);
    return null;
  }

  logWithFixedLabelWidth("getNextServiceInstance", `Selected instance for ${serviceName} - ${serviceInstance.ip}`);
  logMsg(`Selected instance for ${serviceName} - ${serviceInstance.ip}`);
  return serviceInstance;
};

const getService = async (serviceName) => {
  try {
    const response = await axios.get("http://service_discovery:3000/services");
    const services = response.data;
    const serviceInstances = services.filter((service) => service.name === serviceName);

    if (serviceInstances.length === 0) {
      logWithFixedLabelWidth("getService", `No instances found for service: ${serviceName}`);
      logMsg(`No instances found for service: ${serviceName}`);
      return null;
    }

    const nextServiceInstance = await getNextServiceInstance(serviceName, serviceInstances);
    logWithFixedLabelWidth("getService", `Selected instance for ${serviceName} - ${nextServiceInstance.ip}`);
    logMsg(`Selected instance for ${serviceName} - ${nextServiceInstance.ip}`);
    return nextServiceInstance;
  } catch (err) {
    errorWithFixedLabelWidth("getService", "Failed to get service:", err.message);
    logMsg(`Failed to get service ${serviceName}: ${err.message}`);
    return null;
  }
};

const requestWithRetries = async (url, method, data, headers, retries = MAX_RETRIES) => {
  try {
    const response = await axios({
      method: method,
      url: url,
      data: data,
      headers: headers
    });
    return response;
  } catch (error) {
    lastError = error;

    if (error.response?.status >= 400 && error.response?.status < 500)
    {
      return error.response;
    } 
    
    if (retries > 0 && error.response?.status >= 500) {
      logWithFixedLabelWidth("requestWithRetries", `Retrying request to ${url}. Attempts left: ${retries}`);
      logMsg(`Retrying request to ${url}. Attempts left: ${retries}`);
      return await requestWithRetries(url, method, data, headers, retries - 1);
    } else {
      // Break the circuit for the failed service instance after maximum retries
      if (lastError) {
        const failedIp = new URL(url).hostname;
        await cacheSetValue(`circuit:${failedIp}`, '0');
        errorWithFixedLabelWidth("requestWithRetries", `Max retries reached, service at ${failedIp} is unavailable`, '');
        logMsg(`Max retries reached, service at ${failedIp} is unavailable`);
      }

      throw lastError;
    }
  }
};

const redirectRequest = async (serviceName, method, endpoint, data, headers, maxRedirects = MAX_REDIRECTS) => {
  let currentRedirects = 0;
  let lastError = null;
  
  while (currentRedirects < maxRedirects) {
    // Get the next available service instance using getService
    const service = await getService(serviceName);

    if (!service) {
      errorWithFixedLabelWidth("redirectRequest", `No available ${serviceName} instances`, '');
      logMsg(`No available ${serviceName} instances`);
      throw new Error(`No available ${serviceName} instances`);
    }

    const url = `http://${service.ip}:${service.port}${endpoint}`;
    try {
      const response = await requestWithRetries(url, method, data, headers);

      if (shouldCache(endpoint, response.status)) {
        cacheSetValue(endpoint, JSON.stringify(response.data), 60);
      }

      return response;
    } catch (error) {
      lastError = error;
      errorWithFixedLabelWidth("redirectRequest", `Request to ${service.ip}:${service.port} failed, redirecting. Redirects left: ${maxRedirects - currentRedirects - 1}`, '');
      logMsg(`Request to ${service.ip}:${service.port} failed, redirecting. Redirects left: ${maxRedirects - currentRedirects - 1}`);
      currentRedirects++;
    }
  }

  throw new Error(`${currentRedirects} instances of ${serviceName} failed to process the request`);
};

app.use("/users", cacheMiddleware, async (req, res, next) => {
  let response;
  try {
    response = await redirectRequest('user_management_service', req.method, req.originalUrl, req.body, req.headers);
    res.json(response.data);
  } catch (err) {
    errorWithFixedLabelWidth("usersRoute", "Request failed:", err.message);
    logMsg(`Request to user_management_service failed: ${err.message}`);
    res.status(503).json({ message: `Unable to process the request`, last_error: err.message });
  }
});

app.use("/game", cacheMiddleware, async (req, res, next) => {
  try {
    const response = await redirectRequest('game_engine_service', req.method, req.originalUrl, req.body, req.headers);
    res.json(response.data);
  } catch (err) {
    errorWithFixedLabelWidth("gameRoute", "Request failed:", err.message);
    logMsg(`Request to game_engine_service failed: ${err.message}`);
    res.status(503).json({ message: `Unable to process the request`, last_error: err.message });
  }
});

app.get("/status", (req, res) => {
  res.json({ status: "Gateway is up and running!" });
  logMsg("Gateway status checked: up and running");
});

const registerService = async () => {
  try {
    const response = await axios.post(
      "http://service_discovery:3000/register",
      {
        name: "gateway",
        ip: "gateway",
        port: PORT,
      }
    );
    console.log("Service registered successfully:", response.data);
    logMsg("Service registered successfully");
  } catch (err) {
    console.error("Failed to register service:", err);
    logMsg(`Failed to register service: ${err.message}`);
    setTimeout(registerService, 5000); 
  }
};

app.listen(PORT, () => {
  console.log(`Gateway listening on port ${PORT}`);
  logMsg(`Gateway listening on port ${PORT}`);
  registerService();
});
