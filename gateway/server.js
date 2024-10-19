const redis = require('redis');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const CircuitBreaker = require('opossum');

const app = express();
const PORT = process.env.PORT || 5000;

const redisClient = redis.createClient({
    url: 'redis://redis:6379',
});

redisClient.connect().catch((err) => {
    console.error("Redis connection error:", err);
});


const cacheMiddleware = async (req, res, next) => {
    if (req.method !== 'GET') {
        return next();
    }

    const cacheKey = req.originalUrl;
    console.log(`Checking cache for: ${cacheKey}`);
    try {
        const cachedData = await redisClient.get(cacheKey);

        if (cachedData) {
            console.log('Serving from cache for:', cacheKey);
            return res.status(200).json(JSON.parse(cachedData));
        } else {
            console.log('Cache miss for:', cacheKey);
            next();
        }
    } catch (err) {
        console.error('Redis error:', err);
        next();
    }
};

const shouldCache = (req, res) => {
    // Cache only /users and /game/questions endpoints
    return (req.originalUrl ==='/users' || req.originalUrl === '/game/questions') && res.statusCode === 200;
};

const circuitBreakerOptions = {
    timeout: 10000, 
    errorThresholdPercentage: 50,
    resetTimeout: 60000 
};

const proxyBreaker = new CircuitBreaker(async (req, res, next) => {
    next();
}, circuitBreakerOptions);

proxyBreaker.fallback((req, res) => {
    res.status(503).json({ error: 'Service unavailable' });
});

proxyBreaker.on('open', () => console.log('Circuit breaker opened'));
proxyBreaker.on('halfOpen', () => console.log('Circuit breaker half-open'));
proxyBreaker.on('close', () => console.log('Circuit breaker closed'));

app.use('/users', cacheMiddleware, (req, res, next) => {
    proxyBreaker.fire(req, res, next);
}, createProxyMiddleware({
    target: 'http://user_management_service:5002',
    changeOrigin: true,
    onProxyRes: async (proxyRes, req, res) => {
        const body = await streamToString(proxyRes);
        const cacheKey = req.originalUrl;
        if (shouldCache(req, res)) {
            await redisClient.setEx(cacheKey, 360, body);
        }
    },
}));

app.use('/game', cacheMiddleware, (req, res, next) => {
    proxyBreaker.fire(req, res, next);
}, createProxyMiddleware({
    target: 'http://game_engine_service:5003',
    changeOrigin: true,
    onProxyRes: async (proxyRes, req, res) => {
        const body = await streamToString(proxyRes);
        const cacheKey = req.originalUrl;
        if (shouldCache(req, res)) {
            await redisClient.setEx(cacheKey, 360, body);
        }
    }
}));

app.get('/status', (req, res) => {
    res.json({ status: 'Gateway is up and running!' });
});

const streamToString = (stream) => {
    return new Promise((resolve, reject) => {
        const chunks = [];
        stream.on('data', chunk => {
            chunks.push(Buffer.from(chunk));
        });
        stream.on('error', reject);
        stream.on('end', () => {
            resolve(Buffer.concat(chunks).toString('utf8'));
        });
    });
};

app.listen(PORT, () => {
    console.log(`Gateway listening on port ${PORT}`);
});