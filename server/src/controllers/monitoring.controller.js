// controllers/monitoring.controller.js
const systemSvc = require("../services/system.service");
const { success, systemfailure } = require("../utils/response");

exports.getResources = async (req, res) => {
  try {
    const resources = await systemSvc.getResources();
    return success(res, { resources });
  } catch (err) {
    return systemfailure(res, err);
  }
};

exports.getServices = async (req, res) => {
  try {
    const services = await systemSvc.getServices();
    return success(res, { services });
  } catch (err) {
    return systemfailure(res, err);
  }
};

exports.getPerformance = async (req, res) => {
  try {
    const metrics = await systemSvc.getPerformance();
    return success(res, { metrics });
  } catch (err) {
    return systemfailure(res, err);
  }
};
