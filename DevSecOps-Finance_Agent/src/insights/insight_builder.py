"""
Week3 Role B — Top Driver Analyzer & Insight Builder.

- 단일 책임: extract_top_drivers(비용 상위 3개), build_insights(3종 insight 통합).
- Deterministic: 동일 입력 → 동일 출력. 입력 객체를 변경하지 않음.
- JSON 직렬화 가능한 구조만 반환.
"""

from ._rounding import round_value
from .sensitivity import compute_sensitivity
from .tradeoff_engine import generate_tradeoffs

# 반올림 시 소수 자릿수 (공통 규칙)
TOP_N_DRIVERS = 3


def extract_top_drivers(cost_breakdown: dict) -> list[dict]:
    """
    비용 breakdown에서 상위 N개 드라이버를 비용 내림차순으로 반환합니다.

    입력 dict는 수정하지 않습니다. 반환 리스트와 내부 dict는 새로 생성됩니다.
    percentage = (cost / total_cost) * 100, 소수 자릿수는 공통 반올림 규칙 적용.

    Args:
        cost_breakdown: 드라이버명(str) → 비용(number) 매핑.
            예: {"CloudWatchLogs": 43.21, "S3Storage": 22.11, ...}

    Returns:
        최대 TOP_N_DRIVERS(3)개 항목의 리스트. 각 항목은
        {"driver": str, "cost": float, "percentage": float} 형태.
        비용이 0이면 percentage는 0.0으로 고정.
    """
    if not cost_breakdown:
        return []

    total = sum(float(c) for c in cost_breakdown.values())
    zero_total = total == 0

    items = [
        {
            "driver": k,
            "cost": round_value(float(v)),
            "percentage": 0.0 if zero_total else round_value(float(v) / total * 100),
        }
        for k, v in cost_breakdown.items()
    ]

    # 비용 내림차순 정렬. 정렬된 새 리스트 반환 (원본 리스트 변경 없음)
    sorted_items = sorted(items, key=lambda x: x["cost"], reverse=True)
    return sorted_items[:TOP_N_DRIVERS]


def build_insights(
    request: dict,
    pricing_result: dict,
    decision_result: dict,
    policy: dict,
    normalized_assumptions: dict,
) -> dict:
    """
    Public entry point. Top drivers, Sensitivity, Trade-offs를 합쳐 insights 객체를 반환합니다.

    audit 기록, explainable output, demo에서 사용합니다.
    입력으로 받은 request, pricing_result, decision_result, policy, normalized_assumptions는
    수정하지 않습니다.

    Args:
        request: 원본 요청 (policy_version, assumptions, resource_change 등).
        pricing_result: pricing.compute_costs 반환값 (total, breakdown, top3_drivers).
        decision_result: recommended_action, profile, regulation_weight, service_tier, severity 등.
        policy: 로드된 정책 (pricing_table 등).
        normalized_assumptions: 계약 검증된 가정 (duration_hours, traffic_multiplier 등).

    Returns:
        다음 구조의 dict. 항상 동일 키로 존재합니다.
        {
            "top_drivers": list[dict],   # extract_top_drivers 결과
            "sensitivity": list[dict],   # compute_sensitivity 결과
            "tradeoffs": list[str],     # generate_tradeoffs 결과
        }
    """
    breakdown = pricing_result.get("breakdown", [])
    cost_dict = {b["driver"]: b["cost"] for b in breakdown}
    top_drivers = extract_top_drivers(cost_dict)

    base_total = pricing_result.get("total", 0.0)
    sensitivity = compute_sensitivity(
        request=request,
        policy=policy,
        normalized=normalized_assumptions,
        base_total=base_total,
    )

    tradeoffs = generate_tradeoffs(decision_result)

    return {
        "top_drivers": top_drivers,
        "sensitivity": sensitivity,
        "tradeoffs": tradeoffs,
    }
