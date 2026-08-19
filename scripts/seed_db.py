from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.services.bootstrap import init_db  # noqa: E402

if __name__ == "__main__":
    init_db()
    print("seed ok: demo / demo123")
