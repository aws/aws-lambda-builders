//included
const request = require('minimal-request-promise');
exports.handler = async (event, context) => {
	const result = await(request.get(event.url));
	return request;
};
