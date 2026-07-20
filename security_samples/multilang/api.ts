// INTENTIONALLY INSECURE — TypeScript fixture (Semgrep typescript rules).

import { exec } from "child_process";

export function handleRequest(req: { query: Record<string, string> }): void {
  const dir = req.query.dir;
  // Semgrep: command injection via string concatenation into exec
  exec("ls -la " + dir, (err, stdout) => {
    console.log(stdout);
  });
}

export function buildQuery(userId: string): string {
  // Semgrep: SQL injection via template string
  return `SELECT * FROM accounts WHERE id = ${userId}`;
}

// Semgrep: hardcoded secret
const JWT_SECRET = "s3cr3t-hardcoded-key-do-not-ship";
export { JWT_SECRET };
