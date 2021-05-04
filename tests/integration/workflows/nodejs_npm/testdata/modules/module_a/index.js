const module_b = require('@mockcompany/module-b');

exports.sayHello = function() {
  return 'hello from module a! module b says: ' + module_b.sayHello();
}