// INTENTIONALLY INSECURE — JavaScript fixture.
// Triggers Semgrep (JS rules) and CodeQL (javascript-security-extended).

const express = require("express");
const cp = require("child_process");
const mysql = require("mysql");

const app = express();

app.get("/user", (req, res) => {
  // CodeQL / Semgrep: SQL injection — req.query (source) into query (sink)
  const name = req.query.name;
  const conn = mysql.createConnection({ host: "localhost", user: "root" });
  conn.query("SELECT * FROM users WHERE name = '" + name + "'", (e, rows) => {
    res.json(rows);
  });
});

app.get("/ping", (req, res) => {
  // CodeQL / Semgrep: command injection via child_process.exec
  cp.exec("ping " + req.query.host, (e, out) => res.send(out));
});

app.get("/eval", (req, res) => {
  // Semgrep: dangerous eval of user input
  res.send(String(eval(req.query.expr)));
});

module.exports = app;
