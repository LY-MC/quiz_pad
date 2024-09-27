const redis = require('redis');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

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



app.use('/users', cacheMiddleware, createProxyMiddleware({
    target: 'http://user_management_service:5002',
    changeOrigin: true,
    onProxyRes: async (proxyRes, req, res) => {
        const body = await streamToString(proxyRes);
        const cacheKey = req.originalUrl;
        await redisClient.setEx(cacheKey, 360, body);
    },
}));

app.use('/game', cacheMiddleware, createProxyMiddleware({
    target: 'http://game_engine_service:5003',
    changeOrigin: true,
    onProxyRes: async (proxyRes, req, res) => {
        const body = await streamToString(proxyRes);
        const cacheKey = req.originalUrl;
        await redisClient.setEx(cacheKey, 360, body);
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