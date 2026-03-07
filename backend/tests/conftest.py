import os
import sys
from pathlib import Path

"""
테스트 공통 설정.

- 앱 import 경로를 backend 루트로 고정
- 실제 비밀값 없이도 테스트 모듈 import 가 가능하도록 기본 환경변수 주입
"""


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://:test@localhost:6379/0")
os.environ.setdefault("KIS_APP_KEY", "test-app-key")
os.environ.setdefault("KIS_APP_SECRET", "test-app-secret")
os.environ.setdefault("KIS_ACCOUNT_NO", "00000000-00")
os.environ.setdefault("KIS_BASE_URL", "https://example.com")
