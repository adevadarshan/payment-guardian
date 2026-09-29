# Slice 1 dev helper (Windows PowerShell). Run from backend/.
# Requires: Python 3.11+, PostgreSQL URL in .env (or SQLite fallback), node for web/.

# 1. Install
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 2. Configure
Copy-Item .env.example .env   # then edit DATABASE_URL if using Postgres

# 3. Migrate
alembic upgrade head

# 4. Serve (from backend/)
uvicorn app.main:app --reload --port 8000

# 5. Test
pytest -q
