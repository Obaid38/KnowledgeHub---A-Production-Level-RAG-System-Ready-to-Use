// services/minio.service.js
const Minio  = require("minio");
const config = require("../config");
const { logger } = require("../loaders/logging");

const client = new Minio.Client({
  endPoint:  config.minio.endPoint,
  port:      config.minio.port,
  useSSL:    config.minio.useSSL,
  accessKey: config.minio.accessKey,
  secretKey: config.minio.secretKey,
});

// Separate client for presigned URL generation using the public endpoint.
// When MINIO_PUBLIC_ENDPOINT is set (e.g. RunPod proxy URL), presigned URLs
// are signed against the public hostname so browsers can access them directly.
// Falls back to the same config as `client` for local development.
const _publicBase = new URL(config.minio.publicEndpoint);
const publicClient = new Minio.Client({
  endPoint:  _publicBase.hostname,
  port:      Number(_publicBase.port) || (_publicBase.protocol === "https:" ? 443 : 80),
  useSSL:    _publicBase.protocol === "https:",
  accessKey: config.minio.accessKey,
  secretKey: config.minio.secretKey,
});

const BUCKET = config.minio.bucket;

/**
 * Ensure the bucket exists; called once at startup.
 */
async function ensureBucket() {
  try {
    const exists = await client.bucketExists(BUCKET);
    if (!exists) {
      await client.makeBucket(BUCKET, "us-east-1");
      logger.info(`MinIO bucket "${BUCKET}" created.`);
    }
  } catch (err) {
    logger.warn(`MinIO bucket check failed: ${err.message}`);
  }
}

/**
 * Upload a file buffer to MinIO.
 * Returns the object name (key) stored.
 */
async function uploadFile({ buffer, originalName, mimetype, folder = "documents" }) {
  const ext       = originalName.split(".").pop();
  const objectName = `${folder}/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

  await client.putObject(BUCKET, objectName, buffer, buffer.length, {
    "Content-Type": mimetype,
    "x-original-name": encodeURIComponent(originalName),
  });

  return objectName;
}

/**
 * Generate a presigned download URL (default 15 min expiry).
 */
async function presignedUrl(objectName, expirySeconds = 900) {
  return publicClient.presignedGetObject(BUCKET, objectName, expirySeconds);
}

/**
 * Delete a single object from MinIO.
 */
async function deleteFile(objectName) {
  await client.removeObject(BUCKET, objectName);
}

/**
 * Delete multiple objects from MinIO.
 */
async function deleteFiles(objectNames) {
  if (!objectNames.length) return;
  await client.removeObjects(BUCKET, objectNames);
}

module.exports = { client, ensureBucket, uploadFile, presignedUrl, deleteFile, deleteFiles };
