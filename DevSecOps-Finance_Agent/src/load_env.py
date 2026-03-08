"""
프로젝트 루트의 .env 파일을 환경 변수로 로드.
python-dotenv 미설치 시 무시.
"""

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv_if_present() -> None:
    """프로젝트 루트의 .env 를 로드. 없거나 dotenv 미설치면 아무것도 안 함."""
    try:
        from dotenv import load_dotenv
        env_path = _PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
