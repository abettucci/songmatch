"""
AWS Lambda entry point using Mangum.

Fix: lifespan="auto" (was "off" — Bug #5 — DB was never initialized in Lambda)
"""

from mangum import Mangum
from app.main import app

# lifespan="auto" ensures init_db() runs during Lambda cold start
handler = Mangum(app, lifespan="auto")
