const nodemailer = require("nodemailer");
const config = require("../config");
const { logger } = require("../loaders/logging");

async function sendErrorAlert(subject, text) {
  try {
    if (
      !config.smtp.host ||
      !config.smtp.user ||
      !config.smtp.pass ||
      !config.smtp.alertsTo
    ) {
      // In dev: just log the alert instead of sending
      logger.warn({
        message: "sendErrorAlert skipped (SMTP not configured)",
        subject,
        text,
      });
      return;
    }

    const transporter = nodemailer.createTransport({
      host: config.smtp.host,
      port: config.smtp.port || 587,
      secure: false,
      auth: { user: config.smtp.user, pass: config.smtp.pass },
    });

    await transporter.sendMail({
      from: `"API Alerts" <${config.smtp.user}>`,
      to: config.smtp.alertsTo,
      subject,
      text,
    });

    logger.info({ message: "Error alert email sent", subject });
  } catch (e) {
    logger.error({ message: "Failed to send alert email", error: e });
  }
}

module.exports = { sendErrorAlert };
