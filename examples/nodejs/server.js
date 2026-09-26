const express = require('express');
const os = require('os');

const app = express();
const PORT = process.env.PORT || 8080;

app.use(express.json());

app.get('/', (req, res) => {
  res.json({
    status: 'success',
    message: 'Hello from Node.js Express Docker Container on Hugging Face!',
    node_version: process.version,
    platform: process.platform,
    arch: process.arch,
    cpus: os.cpus().length,
    free_memory_mb: Math.round(os.freemem() / 1024 / 1024),
    uptime_seconds: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

app.get('/ping', (req, res) => {
  res.json({ message: 'pong from Node.js service', success: true });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Node.js server listening on http://0.0.0.0:${PORT}`);
});
