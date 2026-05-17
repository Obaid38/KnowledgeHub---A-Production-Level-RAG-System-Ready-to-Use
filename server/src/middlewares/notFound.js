// middlewares/notfound.js

module.exports = (req, res) => {
  res.status(404).json({
    status: "Fail",
    systemfailure: false,
    message: `Route not found: ${req.method} ${req.originalUrl}`,
    data: null,
  });
};
