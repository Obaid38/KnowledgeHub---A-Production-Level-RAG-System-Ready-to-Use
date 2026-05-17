// server.js

const http       = require("http");
const app        = require("./app");
const config     = require("./config");
const { connectMongo }  = require("./loaders/mongoose");
const { logger }        = require("./loaders/logging");
const { ensureBucket }  = require("./services/minio.service");
const { initSocket }    = require("./services/socket.service");

// Start the email worker in-process so Bull jobs are actually processed
require("./workers/email.worker");

(async () => {
  try {
    await connectMongo();
    await ensureBucket();

    // Create HTTP server and attach Socket.IO for real-time events
    const server = http.createServer(app);
    initSocket(server);

    server.listen(config.port, () => {
      logger.info({ message: `Server listening on port ${config.port}` });
    });
  } catch (err) {
    logger.error({ message: "Fatal startup error", err });
    process.exit(1);
  }
})();
