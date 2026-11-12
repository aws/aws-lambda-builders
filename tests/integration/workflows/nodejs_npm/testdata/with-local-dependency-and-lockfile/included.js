//included
const localdep = require('local-dependency');
exports.handler = async (event, context) => {
	return localdep;
};