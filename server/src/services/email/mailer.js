// src/services/email/mailer.js

const nodemailer = require("nodemailer");
const { logger } = require("../../loaders/logging");
const config = require("../../config");

const transporter = nodemailer.createTransport({
  host: config.smtp.host,
  port: config.smtp.port,
  secure: false, // Mailtrap sandbox usually false
  auth: {
    user: config.smtp.user,
    pass: config.smtp.pass,
  },
});

async function sendEmail({ from, to, subject, html, text }) {
  const mail = {
    from:
      from ||
      `"${config.emailBrand.fromName}" <${config.emailBrand.fromEmail}>`,
    to,
    subject,
    html,
    text,
  };
  try {
    await transporter.sendMail(mail);
    return true;
  } catch (err) {
    logger.error(`Email send failed: ${err.message}`, err);
    return false;
  }
}

module.exports = { sendEmail };
