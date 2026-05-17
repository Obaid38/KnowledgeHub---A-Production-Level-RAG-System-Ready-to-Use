// app.js

const express = require("express");
const helmet = require("helmet");
const compression = require("compression");
const cors = require("cors");
const swaggerUi = require("swagger-ui-express");
const YAML = require("yaml");
const fs = require("fs");
const path = require("path");
const config = require("./config");
const routes = require("./routes");
const { requestLogger, errorLogger } = require("./middlewares/logging");
const notFound = require("./middlewares/notFound");
const errorHandler = require("./middlewares/errorHandler");
const requestId = require("./middlewares/requestId");

const app = express();

// Core middlewares
app.use(requestId);
app.use(helmet());
app.use(
  cors({
    origin: "*", // allow everything
     methods: ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allowedHeaders: ["Content-Type", "Authorization"],
  })
);
// Treat requests with no Content-Type as JSON (helpful for Postman / tests)
app.use((req, res, next) => {
  if (req.method !== "GET" && !req.headers["content-type"]) {
    req.headers["content-type"] = "application/json";
  }
  next();
});
app.use(express.json({ limit: "10mb" }));
app.use(express.urlencoded({ extended: true, limit: "10mb" }));
app.use(compression());

// Auto logging (request/response)
app.use(requestLogger);

// Routes
app.use("/api/v1", routes);

const spec = YAML.parse(
  fs.readFileSync(path.join(__dirname, "openapi.yaml"), "utf8")
);
spec.info = spec.info || {};
spec.info.title = `${config.companyProfile.brand.appName} API`;

app.use("/docs", swaggerUi.serve, swaggerUi.setup(spec));
// optional: raw JSON
app.get("/docs.json", (_req, res) => res.json(spec));

// 404 & error handling
app.use(notFound);
app.use(errorLogger); // logs stack traces with winston
app.use(errorHandler);

module.exports = app;
