'use strct'

const fs = require('fs')
const path = require('path')

fs.writeFileSync(path.join(__dirname, 'postbuild.txt'), 'Postbuild', 'utf8')