// config/index.js
require("dotenv").config();
const { loadCompanyProfile } = require("./companyProfile");

const get    = (key, def) => process.env[key] ?? def;
const getNum = (key, def) => {
  const v = process.env[key];
  if (v === undefined || v === "") return def;
  const n = Number(v);
  return Number.isFinite(n) ? n : def;
};
const getBool = (key, def) => {
  const v = process.env[key];
  if (v === undefined || v === "") return def;
  return v === "true";
};

const companyProfile = loadCompanyProfile();

const config = {
  env:    get("NODE_ENV", "development"),
  appEnv: get("APP_ENV",  "development"),
  port:   getNum("PORT",  7000),

  mongoUri: get("MONGO_URI", "mongodb://localhost:27017/insight-hub"),
  logLevel: get("LOG_LEVEL", "info"),

  jwt: {
    secret:      get("JWT_SECRET",     "change_me_in_production"),
    expiresIn:   get("JWT_EXPIRES_IN", "7d"),
    mfaSecret:   get("MFA_JWT_SECRET", "mfa_change_me"),
    mfaExpiresIn: "5m", // short-lived token for the MFA step
  },

  passwordReset: {
    expiryMinutes: getNum("PASSWORD_RESET_EXPIRY_MINUTES", 60),
  },

  redis: {
    url:  get("REDIS_URL",  null),
    host: get("REDIS_HOST", "127.0.0.1"),
    port: getNum("REDIS_PORT", 6379),
  },

  smtp: {
    host:     get("SMTP_HOST", "sandbox.smtp.mailtrap.io"),
    port:     getNum("SMTP_PORT", 2525),
    user:     get("SMTP_USER"),
    pass:     get("SMTP_PASS"),
    alertsTo: get("ALERTS_TO"),
  },

  emailBrand: {
    fromName:     get("EMAIL_FROM_NAME", companyProfile.brand.appName),
    fromEmail:    get("EMAIL_FROM",      companyProfile.contact.noReplyEmail),
    supportEmail: get("SUPPORT_EMAIL",   companyProfile.contact.supportEmail),
    appName:      get("APP_NAME",        companyProfile.brand.appName),
    clientUrl:    get("CLIENT_URL",      "http://localhost:3000"),
  },

  minio: {
    endPoint:        get("MINIO_ENDPOINT",    "localhost"),
    port:            getNum("MINIO_PORT",      9000),
    useSSL:          getBool("MINIO_USE_SSL",  false),
    accessKey:       get("MINIO_ACCESS_KEY",  "minioadmin"),
    secretKey:       get("MINIO_SECRET_KEY",  "minioadmin"),
    bucket:          get("MINIO_BUCKET",      "insight-hub-docs"),
    publicEndpoint:  get("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000"),
  },

  ai: {
    baseUrl:       get("AI_SERVICE_URL",          "http://localhost:8000"),
    ingestUrl:     get("AI_INGEST_URL",           "http://localhost:8000"),
    timeout:       getNum("AI_SERVICE_TIMEOUT_MS",        120000),
    ingestTimeout: getNum("AI_INGEST_TIMEOUT_MS",         600000),
  },

  qdrant: {
    url: get("QDRANT_URL", "http://localhost:6333"),
  },

  cors: {
    allowedOrigins: (get("CORS_ALLOWED_ORIGINS", "http://localhost:3000") || "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  },

  companyProfile,
};

module.exports = config;
