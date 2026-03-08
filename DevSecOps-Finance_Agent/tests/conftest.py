"""Pytest configuration: ensure project root is on path, load .env."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

# .env 로드 (테스트 시에도 USE_AWS_PRICING_API 등 적용)
try:
    from dotenv import load_dotenv
    env_path = root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass
