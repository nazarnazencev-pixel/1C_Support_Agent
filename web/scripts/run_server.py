import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import uvicorn


web_root = Path(__file__).resolve().parents[1]
backend_root = web_root.parent / "1C_Support_Agent"
load_dotenv(web_root / ".env", override=True)
sys.path.insert(0, str(backend_root))
sys.path.insert(0, str(web_root))
os.chdir(backend_root)


if __name__ == "__main__":
    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, workers=1)
