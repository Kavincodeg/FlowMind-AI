"""
Export FastAPI OpenAPI schema to openapi.json in root directory.
Used by frontend build and type generation (openapi-typescript).
"""
import json
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from backend.api.main import app


def main():
    schema = app.openapi()
    out_path = root_dir / "openapi.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    print(f"Exported OpenAPI schema to openapi.json with {len(schema.get('paths', {}))} endpoints.")


if __name__ == "__main__":
    main()
