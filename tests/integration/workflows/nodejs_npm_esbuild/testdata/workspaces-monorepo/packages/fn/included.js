const request = require('minimal-request-promise');

module.exports = () => typeof request.get;
