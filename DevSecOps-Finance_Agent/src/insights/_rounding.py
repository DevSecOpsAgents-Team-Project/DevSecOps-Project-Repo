"""
공통 반올림 규칙. 모든 explainability 모듈에서 동일한 소수 자릿수 사용.
Deterministic: round(half-even) 사용.
"""

ROUND_DECIMALS = 2


def round_value(value: float, decimals: int | None = None) -> float:
    """
    숫자를 지정된 소수 자릿수로 반올림합니다.
    모듈 전반에서 반올림 방식을 통일하기 위해 사용합니다.

    Args:
        value: 반올림할 숫자.
        decimals: 소수 자릿수. None이면 ROUND_DECIMALS(2) 사용.

    Returns:
        반올림된 float. 동일 입력에 대해 항상 동일 출력 (deterministic).
    """
    if decimals is None:
        decimals = ROUND_DECIMALS
    return round(float(value), decimals)
