"""Write the API's OpenAPI schema to frontend/openapi.json (input for `npm run gen:api`)."""

import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://unused@localhost/unused")

from app.main import app  # noqa: E402

out = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
print(f"wrote {out}")
