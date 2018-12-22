'use strct'

const fs = require('fs')
const path = require('path')

fs.writeFileSync(path.join(__dirname, 'prebuild.txt'), 'Prebuild', 'utf8')
fs.writeFileSync(path.join(__dirname, 'prebuild.js'), 'Prebuild', 'utf8')
