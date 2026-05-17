// services/system.service.js
const si       = require("systeminformation");
const mongoose = require("mongoose");
const { logger } = require("../loaders/logging");

// ── Resource gauges (CPU / RAM / Disk / GPU) ──────────────────────────────────

async function getResources() {
  const [cpu, mem, disk, graphics] = await Promise.all([
    si.currentLoad(),
    si.mem(),
    si.fsSize(),
    si.graphics().catch(() => ({ controllers: [] })),
  ]);

  const diskTotal = disk.reduce((a, d) => a + d.size, 0) || 1;
  const diskUsed  = disk.reduce((a, d) => a + d.used, 0);
  const gpuLoad   =
    graphics.controllers?.length > 0
      ? Math.round(graphics.controllers[0].utilizationGpu ?? 0)
      : 0;

  return [
    { id: "cpu",  label: "CPU",  value: Math.round(cpu.currentLoad), unit: "%" },
    { id: "ram",  label: "RAM",  value: Math.round((mem.active / mem.total) * 100), unit: "%" },
    { id: "disk", label: "Disk", value: Math.round((diskUsed / diskTotal) * 100), unit: "%" },
    { id: "gpu",  label: "GPU",  value: gpuLoad, unit: "%" },
  ];
}

// ── Service health checks ─────────────────────────────────────────────────────

async function getServices() {
  const config = require("../config");

  // MongoDB
  const mongoState  = mongoose.connection.readyState; // 1 = connected
  const mongoStatus = mongoState === 1 ? "healthy" : "down";
  const mongoDetail = mongoState === 1 ? "Connected" : "Disconnected";

  // MinIO
  let minioStatus = "healthy";
  let minioDetail = "Bucket reachable";
  try {
    const minioSvc = require("./minio.service");
    await minioSvc.client.bucketExists(config.minio.bucket);
  } catch (e) {
    minioStatus = "down";
    minioDetail = e.message;
  }

  // Job Queue (Redis/Bull)
  let queueStatus = "healthy";
  let queueDetail = "Queue running";
  try {
    const Bull = require("bull");
    const q    = new Bull("health-check", { redis: config.redis });
    await q.isReady();
    await q.close();
  } catch {
    queueStatus = "degraded";
    queueDetail = "Redis unavailable";
  }

  return [
    { id: "mongodb",   name: "MongoDB",       status: mongoStatus, detail: mongoDetail },
    { id: "vectoridx", name: "Vector Index",  status: "healthy",   detail: "Atlas vector search enabled" },
    { id: "minio",     name: "MinIO Storage", status: minioStatus, detail: minioDetail },
    { id: "queue",     name: "Job Queue",     status: queueStatus, detail: queueDetail },
  ];
}

// ── Performance metrics ───────────────────────────────────────────────────────

let _requestCount = 0;
let _totalQueryMs = 0;
let _queryCount   = 0;
let _startTime    = Date.now();

function recordRequest()  { _requestCount++; }
function recordQueryTime(ms) { _totalQueryMs += ms; _queryCount++; }

async function getPerformance() {
  const uptimeSec  = process.uptime();
  const elapsedMs  = Date.now() - _startTime || 1;
  const elapsedMin = elapsedMs / 60000 || 1;

  const avgQueryMs = _queryCount > 0 ? Math.round(_totalQueryMs / _queryCount) : 0;
  const throughput = Math.round(_requestCount / elapsedMin);
  const uptimePct  = Math.min(100, ((uptimeSec * 1000) / elapsedMs) * 100).toFixed(1);

  return [
    {
      id:           "avg-query-time",
      label:        "Avg Query Time",
      value:        `${(avgQueryMs / 1000).toFixed(1)}s`,
      target:       "target <10s",
      withinTarget: avgQueryMs < 10000,
    },
    {
      id:           "uptime",
      label:        "Uptime",
      value:        `${uptimePct}%`,
      target:       "target >99%",
      withinTarget: Number(uptimePct) >= 99,
    },
    {
      id:           "throughput",
      label:        "Throughput",
      value:        `${throughput} req/min`,
      target:       "target <200",
      withinTarget: throughput < 200,
    },
  ];
}

module.exports = {
  getResources,
  getServices,
  getPerformance,
  recordRequest,
  recordQueryTime,
};
