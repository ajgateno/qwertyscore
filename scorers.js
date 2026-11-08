// Score words with the original third-party JavaScript scorers, unmodified.
//
// Usage: node scorers.js <word-cost index.js> <carpalx src dir> < words.txt
// Reads one word per line on stdin, writes CSV "word,word_cost,carpalx" to stdout.
//
// - word-cost (stutrek/word-cost): its index.js is a browser script that also
//   wires up jQuery UI, so it runs in a sandbox with a stub `$` and only its
//   calculateScore() is used.
// - carpalx.js (dmtrs/carpalx.js): its effort model scores triads (3-letter
//   windows). A word's effort is the sum of its triads' efforts, as carpalx
//   sums triads over a document. Words shorter than 3 letters have no triads,
//   so their carpalx score is left blank.

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const readline = require("readline");

const [wordCostPath, carpalxDir] = process.argv.slice(2);

// --- word-cost -------------------------------------------------------------
const stub = () => ({ on() {}, html() {}, val() { return ""; }, then() {} });
stub.getJSON = stub;
const sandbox = { $: stub, console };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(wordCostPath, "utf8"), sandbox);
const wordCost = sandbox.calculateScore;

// --- carpalx ---------------------------------------------------------------
const utils = require(path.resolve(carpalxDir, "utils.js"));
const { qwerty } = require(path.resolve(carpalxDir, "layout.js"));
const triadEffort = utils.e(qwerty);

function carpalx(word) {
  if (word.length < 3) return "";
  let total = 0;
  for (let i = 0; i + 3 <= word.length; i++) total += triadEffort(word.slice(i, i + 3));
  return total.toFixed(4);
}

// --- main ------------------------------------------------------------------
const rl = readline.createInterface({ input: process.stdin, terminal: false });
const out = ["word,word_cost,carpalx"];
rl.on("line", (line) => {
  const w = line.trim().toLowerCase();
  if (w) out.push(`${w},${wordCost(w)},${carpalx(w)}`);
});
rl.on("close", () => process.stdout.write(out.join("\n") + "\n"));
