const fs = require("fs");
const path = require("path");
const Handlebars = require("handlebars");
const config = require("../../config");

let compiled = null;

function loadTemplates() {
  if (compiled) return compiled;

  // register partials
  const partialsDir = path.join(__dirname, "../../emailTemplates/partials");
  const partialFiles = fs.readdirSync(partialsDir);
  partialFiles.forEach((file) => {
    if (!file.endsWith(".hbs")) return;
    const name = file.replace(".hbs", "");
    const content = fs.readFileSync(path.join(partialsDir, file), "utf8");
    Handlebars.registerPartial(name, content);
  });

  // compile templates
  const templatesDir = path.join(__dirname, "../../emailTemplates");
  const map = {};
  fs.readdirSync(templatesDir).forEach((file) => {
    if (!file.endsWith(".hbs")) return;
    if (file.startsWith("_")) return; // skip partials at root, if any
    const key = file.replace(".hbs", "");
    const content = fs.readFileSync(path.join(templatesDir, file), "utf8");
    map[key] = Handlebars.compile(content);
  });

  compiled = map;
  return compiled;
}

function render(templateName, vars) {
  const templates = loadTemplates();
  const t = templates[templateName];
  if (!t) throw new Error(`Email template not found: ${templateName}`);
  const defaults = {
    app_name: config.emailBrand.appName,
    support_email: config.emailBrand.supportEmail,
  };
  return t({ ...defaults, ...vars });
}

module.exports = { render };
