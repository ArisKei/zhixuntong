from pathlib import Path
import sys

APP_DIR = Path(__file__).resolve().parent
API_DIR = APP_DIR.parent
REPO_ROOT = API_DIR.parent.parent
PACKAGES_DIR = REPO_ROOT / "packages"
NOTIFY_SRC_DIR = REPO_ROOT / "services" / "notify" / "src"

for candidate in (str(PACKAGES_DIR), str(NOTIFY_SRC_DIR), str(API_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)
