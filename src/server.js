'use strict';

const http = require('node:http');
const { createApp } = require('./app');

const PORT = Number(process.env.PORT) || 3000;

http.createServer(createApp()).listen(PORT, () => {
  console.log(`NOVAHAUS shop running at http://localhost:${PORT}`);
});
