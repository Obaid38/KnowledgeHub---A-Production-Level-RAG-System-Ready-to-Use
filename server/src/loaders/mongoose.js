// loaders/mongoose.js

const mongoose = require("mongoose");
const config = require("../config");
const { logger } = require("./logging");

async function connectMongo() {
  mongoose.set("strictQuery", true);

  mongoose.connection.on("connected", () => {
    logger.info({ message: "MongoDB connected" });
  });

  mongoose.connection.on("error", (err) => {
    logger.error({ message: "MongoDB connection error", err });
  });

  mongoose.connection.on("disconnected", () => {
    logger.warn({ message: "MongoDB disconnected" });
  });

  return mongoose.connect(config.mongoUri, {
    autoIndex: config.env !== "production",
    maxPoolSize: 10,
  });
}

module.exports = { connectMongo };
