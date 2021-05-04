const module_c = require('@mockcompany/module-c');

exports.sayHello = function() {
  return 'hello from module b! module-c says: ' + module_c.sayHello();
}