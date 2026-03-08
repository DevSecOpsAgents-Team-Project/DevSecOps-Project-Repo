"""
Week3 Role B: Explainability modules.

- build_insights: Public entry point. top_drivers, sensitivity, tradeoffs를 담은 insights dict 반환.
- extract_top_drivers: 비용 breakdown에서 상위 N개 드라이버 추출.
- compute_sensitivity: 파라미터 변경 시나리오별 비용 변화 계산.
- generate_tradeoffs: context 조건별 Trade-off 문장 생성.

전체 모듈은 deterministic 동작을 보장합니다. 동일 입력 → 동일 출력.
"""

from .insight_builder import build_insights, extract_top_drivers
from .sensitivity import compute_sensitivity
from .tradeoff_engine import generate_tradeoffs

__all__ = [
    "build_insights",
    "extract_top_drivers",
    "compute_sensitivity",
    "generate_tradeoffs",
]
