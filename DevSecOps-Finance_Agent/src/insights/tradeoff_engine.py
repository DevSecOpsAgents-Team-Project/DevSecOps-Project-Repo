"""
Week3 Role B — Trade-off Reasoning Engine.

- 단일 책임: context 조건에 따른 고정 Trade-off 문장 리스트 생성.
- Deterministic: 동일 context → 동일 문장 리스트. context는 읽기만 하며 수정하지 않음.
- 문장 길이 상한으로 가독성/일관성 유지.
"""

# 문장 최대 길이 (면접/문서용 일관성)
MAX_SENTENCE_LEN = 180
# 규제 가중치 문장 출력 임계값
REGULATION_WEIGHT_THRESHOLD = 1.5


def generate_tradeoffs(context: dict) -> list[str]:
    """
    context 값에 따라 결정론적으로 Trade-off 문장 리스트를 생성합니다.

    context는 수정하지 않습니다. 반환 리스트와 문자열은 새로 생성됩니다.
    조건 평가 순서와 문장 내용은 고정되어 있어 동일 입력 시 항상 동일 출력입니다.

    Args:
        context: 다음 키를 가진 dict (없으면 기본값 사용).
            - service_tier: str (예: "S1", "S2", "S3")
            - recommended_action: str (예: "isolate", "log_harden")
            - regulation_weight: number (기본 1.0)
            - profile: str (예: "LeanStartup", "Standard")

    Returns:
        조건에 맞는 문장들의 리스트. 각 문장은 최대 MAX_SENTENCE_LEN(180)자.
        조건1: service_tier == "S1" 이고 recommended_action == "isolate" → 격리 제외 문장
        조건2: regulation_weight >= REGULATION_WEIGHT_THRESHOLD(1.5) → 로그 강화 우선 문장
        조건3: profile == "LeanStartup" → 비용 효율성 문장
    """
    service_tier = context.get("service_tier") or ""
    recommended_action = context.get("recommended_action") or ""
    regulation_weight = _to_float(context.get("regulation_weight"), 1.0)
    profile = context.get("profile") or ""

    sentences: list[str] = []

    if service_tier == "S1" and recommended_action == "isolate":
        sentences.append(_truncate("S1 서비스 계층에서는 가용성 보호를 위해 격리 조치가 제외되었습니다."))

    if regulation_weight >= REGULATION_WEIGHT_THRESHOLD:
        sentences.append(_truncate("규제 가중치가 높아 로그 강화(log_harden)가 우선 고려되었습니다."))

    if profile == "LeanStartup":
        sentences.append(_truncate("LeanStartup 프로파일에서는 비용 효율성이 의사결정에 더 큰 영향을 미칩니다."))

    return sentences


def _to_float(value: str | int | float | None, default: float) -> float:
    """
    context에서 읽은 값을 float으로 변환합니다.
    None, 변환 불가 시 default를 반환합니다. 입력 객체는 수정하지 않습니다.

    Args:
        value: 변환할 값.
        default: value가 None이거나 변환 실패 시 반환할 값.

    Returns:
        float. deterministic.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _truncate(s: str) -> str:
    """
    문자열이 MAX_SENTENCE_LEN을 초과하면 잘라서 "..."을 붙여 반환합니다.
    원본 문자열을 수정하지 않습니다.

    Args:
        s: 원본 문장.

    Returns:
        길이 <= MAX_SENTENCE_LEN인 새 문자열.
    """
    if len(s) <= MAX_SENTENCE_LEN:
        return s
    return s[: MAX_SENTENCE_LEN - 3] + "..."
