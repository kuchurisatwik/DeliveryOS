// INTENTIONALLY INSECURE — Go fixture (Semgrep go rules).
package main

import (
	"database/sql"
	"fmt"
	"net/http"
	"os/exec"
)

func userHandler(w http.ResponseWriter, r *http.Request) {
	name := r.URL.Query().Get("name")

	// Semgrep: SQL injection via fmt.Sprintf into the query
	db, _ := sql.Open("mysql", "user:pass@/app")
	db.Query(fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", name))

	// Semgrep: command injection via exec with untrusted input
	out, _ := exec.Command("sh", "-c", "echo "+r.URL.Query().Get("msg")).Output()
	w.Write(out)
}


func main() {
	http.HandleFunc("/user", userHandler)
	http.ListenAndServe(":8080", nil)
}
