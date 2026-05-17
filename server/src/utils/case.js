const _ = require("lodash");

function toSnakeCaseKey(key) {
	return _.snakeCase(key);
}

function toSnakeCaseDeep(value) {
	if (Array.isArray(value)) {
		return value.map((item) => toSnakeCaseDeep(item));
	}
	if (value && typeof value === "object") {
		const result = {};
		for (const [k, v] of Object.entries(value)) {
			result[toSnakeCaseKey(k)] = toSnakeCaseDeep(v);
		}
		return result;
	}
	return value;
}

module.exports = { toSnakeCaseDeep };
