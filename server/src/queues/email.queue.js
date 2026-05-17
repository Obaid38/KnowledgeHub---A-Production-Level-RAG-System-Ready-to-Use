// src/queues/email.queue.js

const Queue = require("bull");
const config = require("../config");

const redisUrl =
  config.redis.url || `redis://${config.redis.host}:${config.redis.port}`;
const emailQueue = new Queue("email", redisUrl);

emailQueue.on("error", (err) => console.error("[emailQueue] error", err));

async function enqueueEmailJob(payload, opts = {}) {
  // Don’t block the route forever waiting for Redis
  const ready = emailQueue.isReady();
  const timeout = new Promise((_, rej) =>
    setTimeout(() => rej(new Error("emailQueue not ready (timeout)")), 2000)
  );
  await Promise.race([ready, timeout]);

  return emailQueue.add("send", payload, {
    attempts: 5,
    backoff: { type: "exponential", delay: 1000 },
    removeOnComplete: true,
    timeout: 30000,
    ...opts,
  });
}

module.exports = { emailQueue, enqueueEmailJob };
