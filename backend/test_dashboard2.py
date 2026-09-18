import sqlite3
conn = sqlite3.connect("sql_app.db")
c = conn.cursor()
c.execute("SELECT timestamp FROM audit_logs ORDER BY timestamp DESC LIMIT 1")
print("DB raw:", c.fetchone()[0])
conn.close()
