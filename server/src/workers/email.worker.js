// src/workers/email.worker.js

require("dotenv").config();
const { emailQueue } = require("../queues/email.queue");
const { render } = require("../services/email/templateLoader");
const { sendEmail } = require("../services/email/mailer");
const { logger } = require("../loaders/logging");

// NOTE: use the *named* processor: 'send'
emailQueue.process("send", 5, async (job) => {
  const { to, subject, template, variables, from, text } = job.data;

  const html = render(template, variables);
  const ok = await sendEmail({ from, to, subject, html, text });
  if (!ok) throw new Error("Failed to send email");

  return true;
});

emailQueue.on("ready", () => logger.info("[emailQueue] ready"));
emailQueue.on("completed", (job) =>
  logger.info(`[emailQueue] completed ${job.id}`)
);
emailQueue.on("failed", (job, err) =>
  logger.error(`[emailQueue] failed ${job?.id}: ${err?.message}`)
);
