//included
import { muses } from './reference.reference';

process.stdout.write("===\nThe Muses\n===\n\n");
process.stdout.write(muses.map(muse => `\t${muse.name}: ${muse.description}`).join("\n"));

const x = 1;
module.exports = x;
