const redis = require("redis");
const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const CircuitBreaker = require("opossum");
const axios = require("axios");
const rateLimit = require("express-rate-limit");
const loadBalancerUrl = 'http://nginx_load_balancer'; 

const app = express();
const PORT = process.env.PORT || 5000;

const redisClient = redis.createClient({
  url: "redis://redis:6379",
});

redisClient.connect().catch((err) => {
  console.error("Redis connection error:", err);
});

const cacheMiddleware = async (req, res, next) => {
  if (req.method !== "GET") {
    return next();
  }

  const cacheKey = req.originalUrl;
  console.log(`Checking cache for: ${cacheKey}`);
  try {
    const cachedData = await redisClient.get(cacheKey);

    if (cachedData) {
      console.log("Serving from cache for:", cacheKey);
      return res.status(200).json(JSON.parse(cachedData));
    } else {
      console.log("Cache miss for:", cacheKey);
    }
  } catch (err) {
    console.error("Cache error:", err);
  }
  next();
};

const limiter = rateLimit({
  windowMs: 5 * 60 * 1000,
  max: 15,
  message: "Too many requests, please try again later.",
});

app.use(limiter);

const shouldCache = (req, res) => {
  // Cache only /users and /game/questions endpoints
  return (
    (req.originalUrl === "/users" || req.originalUrl === "/game/questions") &&
    res.statusCode === 200
  );
};

const circuitBreakerOptions = {
  timeout: 10000,
  errorThresholdPercentage: 50,
  resetTimeout: 60000,
};

const proxyBreaker = new CircuitBreaker(async (req, res, next) => {
  next();
}, circuitBreakerOptions);

proxyBreaker.fallback((req, res) => {
  res.status(503).json({ error: "Service unavailable" });
});

proxyBreaker.on("open", () => console.log("Circuit breaker opened"));
proxyBreaker.on("halfOpen", () => console.log("Circuit breaker half-open"));
proxyBreaker.on("close", () => console.log("Circuit breaker closed"));

const getService = async (serviceName) => {
  try {
    const response = await axios.get("http://service_discovery:3000/services");
    const services = response.data;
    const service = services.find((s) => s.name === serviceName);
    console.log(`Retrieved service info for ${serviceName}:`, service);
    return service;
  } catch (err) {
    console.error("Failed to get service:", err);
    return null;
  }
};

const createProxy = async (serviceName) => {
  const service = await getService(serviceName);
  if (!service) {
    throw new Error(`${serviceName} service unavailable`);
  }
  const targetUrl = `http://${service.ip}:${service.port}`;
  console.log(`Proxying requests to: ${targetUrl}`);
  return createProxyMiddleware({
    target: targetUrl,
    changeOrigin: true,
    onProxyRes: async (proxyRes, req, res) => {
      const body = await streamToString(proxyRes);
      const cacheKey = req.originalUrl;
      if (shouldCache(req, res)) {
        await redisClient.setEx(cacheKey, 360, body);
      }
    },
  });
};

app.use(
  "/users",
  cacheMiddleware,
  async (req, res, next) => {
    const userService = await getService("user_management_service");
    if (!userService) {
      return res.status(503).json({ error: "User service unavailable" });
    }
    await proxyBreaker.fire(req, res, next);
  },
  async (req, res, next) => {
    const proxy = await createProxy("user_management_service");
    proxy(req, res, next);
  }
);

app.use(
  "/game",
  cacheMiddleware,
  async (req, res, next) => {
    const gameService = await getService("game_engine_service");
    if (!gameService) {
      return res.status(503).json({ error: "Game service unavailable" });
    }
    await proxyBreaker.fire(req, res, next);
  },
  async (req, res, next) => {
    const proxy = await createProxy("game_engine_service");
    proxy(req, res, next);
  }
);

app.get("/status", (req, res) => {
  res.json({ status: "Gateway is up and running!" });
});

const streamToString = (stream) => {
  return new Promise((resolve, reject) => {
    const chunks = [];
    stream.on("data", (chunk) => {
      chunks.push(Buffer.from(chunk));
    });
    stream.on("error", reject);
    stream.on("end", () => {
      resolve(Buffer.concat(chunks).toString("utf8"));
    });
  });
};

const registerService = async () => {
  try {
    const response = await axios.post(
      "http://service_discovery:3000/register",
      {
        name: "gateway",
        ip: "gateway", // Use the service name as the IP address
        port: PORT,
      }
    );
    console.log("Service registered successfully:", response.data);
  } catch (err) {
    console.error("Failed to register service:", err);
    setTimeout(registerService, 5000); // Retry after 5 seconds
  }
};

app.listen(PORT, () => {
  console.log(`Gateway listening on port ${PORT}`);
  registerService();
});
