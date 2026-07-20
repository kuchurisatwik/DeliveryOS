# INTENTIONALLY INSECURE — Ruby fixture (Semgrep ruby + CodeQL ruby).

require "sqlite3"

def find_user(name)
  db = SQLite3::Database.new "app.db"
  # Semgrep / CodeQL: SQL injection via string interpolation
  db.execute("SELECT * FROM users WHERE name = '#{name}'")
end

def ping(host)
  # Semgrep: command injection via system with untrusted input
  system("ping -c 1 #{host}")
end

def render(template)
  # Semgrep: dangerous eval of untrusted input
  eval(template)
end
