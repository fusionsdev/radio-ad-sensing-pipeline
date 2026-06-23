import sqlite3
c = sqlite3.connect("/app/data/pipeline.db")
print("chunks done:", c.execute("SELECT COUNT(*) FROM chunks WHERE status='done'").fetchone()[0])
print("pending:", c.execute("SELECT COUNT(*) FROM chunks WHERE status='pending'").fetchone()[0])
print("processing:", c.execute("SELECT COUNT(*) FROM chunks WHERE status='processing'").fetchone()[0])
print("keyword_hits:", c.execute("SELECT COUNT(*) FROM keyword_hits").fetchone()[0])
recent = c.execute("SELECT keyword, COUNT(*) n FROM keyword_hits GROUP BY keyword ORDER BY n DESC LIMIT 10").fetchall()
print("top keywords:", recent)
c.close()
