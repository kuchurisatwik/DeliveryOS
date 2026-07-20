<?php
// INTENTIONALLY INSECURE — PHP fixture (Semgrep php rules).

// Semgrep: SQL injection via unsanitized request parameter
$name = $_GET['name'];
$conn = new mysqli("localhost", "root", "", "app");
$result = $conn->query("SELECT * FROM users WHERE name = '" . $name . "'");

// Semgrep: command injection via shell_exec on user input
$host = $_GET['host'];
echo shell_exec("ping -c 1 " . $host);

// Semgrep: dangerous eval of user input
eval($_GET['code']);
?>
