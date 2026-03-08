"""
Week3 Role B — Sensitivity Analysis Engine.

- 단일 책임: 파라미터 변경 시나리오별 비용 변화(차액, 증가율) 계산.
- Deterministic: 동일 입력 → 동일 출력. 입력 request/policy/normalized를 변경하지 않음.
- 숫자 반올림은 공통 _rounding 모듈 사용.
"""

from ..pricing import compute_costs

from ._rounding import round_value

# 시나리오 상수 (고정값으로 deterministic 보장)
TRAFFIC_BASE = 1.0
TRAFFIC_VARIANT = 2.0
DURATION_BASE = 24
DURATION_VARIANT = 168
LOG_MULTIPLIER_BASE = 1.5
LOG_MULTIPLIER_VARIANT = 2.0


def compute_sensitivity(
    request: dict,
    policy: dict,
    normalized: dict,
    base_total: float,
) -> list[dict]:
    """
    traffic_multiplier, duration_hours, log_multiplier 3종 시나리오에 대해
    비용 변화(cost_delta, increase_rate_pct)를 계산해 리스트로 반환합니다.

    request, policy, normalized는 읽기만 하며 수정하지 않습니다.
    variant 계산 시 필요한 복사본은 함수 내부에서만 생성합니다.

    Args:
        request: 원본 요청. resource_change 등 참조용.
        policy: 로드된 정책. pricing_table 사용.
        normalized: 정규화된 가정 (duration_hours, traffic_multiplier 등).
        base_total: 기준 비용 (pricing_result["total"]).

    Returns:
        길이 3의 리스트. 각 항목:
        {
            "parameter": str,
            "base": number,
            "variant": number,
            "cost_delta": float,
            "increase_rate_pct": float,
        }
        parameter 순서: traffic_multiplier, duration_hours, log_multiplier.
    """
    resource_change = request.get("resource_change", {})
    pricing_table = policy.get("pricing_table", {})

    if not pricing_table:
        return _empty_sensitivity_list()

    base_total_f = float(base_total)
    out = []

    # 1) traffic_multiplier: base 1.0 → variant 2.0
    variant_asm = {**normalized, "traffic_multiplier": TRAFFIC_VARIANT}
    variant_total = compute_costs(resource_change, variant_asm, pricing_table)["total"]
    out.append(_sensitivity_row("traffic_multiplier", TRAFFIC_BASE, TRAFFIC_VARIANT, variant_total, base_total_f))

    # 2) duration_hours: base 24 → variant 168
    variant_asm_d = {**normalized, "duration_hours": DURATION_VARIANT}
    variant_total_d = compute_costs(resource_change, variant_asm_d, pricing_table)["total"]
    out.append(_sensitivity_row("duration_hours", DURATION_BASE, DURATION_VARIANT, variant_total_d, base_total_f))

    # 3) log_multiplier: base 1.5 → variant 2.0 (cloudwatch_log_gb_per_day 스케일로 반영)
    scale = LOG_MULTIPLIER_VARIANT / LOG_MULTIPLIER_BASE
    base_log_gb = float(resource_change.get("cloudwatch_log_gb_per_day", 0))
    variant_rc = {**resource_change, "cloudwatch_log_gb_per_day": round_value(base_log_gb * scale)}
    variant_total_l = compute_costs(variant_rc, normalized, pricing_table)["total"]
    out.append(
        _sensitivity_row(
            "log_multiplier",
            LOG_MULTIPLIER_BASE,
            LOG_MULTIPLIER_VARIANT,
            variant_total_l,
            base_total_f,
        )
    )

    return out


def _sensitivity_row(
    parameter: str,
    base: float,
    variant: float,
    variant_total: float,
    base_total: float,
) -> dict:
    """
    단일 시나리오에 대한 sensitivity 행을 생성합니다.
    cost_delta, increase_rate_pct는 공통 반올림 규칙 적용.

    Args:
        parameter: 파라미터 이름.
        base: 기준값.
        variant: 변경값.
        variant_total: 변경 후 비용.
        base_total: 기준 비용. 0이면 increase_rate_pct는 0.0.

    Returns:
        {"parameter", "base", "variant", "cost_delta", "increase_rate_pct"} dict.
    """
    cost_delta = round_value(variant_total - base_total)
    if base_total == 0:
        increase_rate_pct = 0.0
    else:
        increase_rate_pct = round_value((cost_delta / base_total) * 100)
    return {
        "parameter": parameter,
        "base": base,
        "variant": variant,
        "cost_delta": cost_delta,
        "increase_rate_pct": increase_rate_pct,
    }


def _empty_sensitivity_list() -> list[dict]:
    """
    pricing_table이 없을 때 반환하는 고정 형태 리스트.
    항상 동일한 3개 항목을 반환하여 deterministic을 유지합니다.
    """
    return [
        {
            "parameter": "traffic_multiplier",
            "base": TRAFFIC_BASE,
            "variant": TRAFFIC_VARIANT,
            "cost_delta": 0.0,
            "increase_rate_pct": 0.0,
        },
        {
            "parameter": "duration_hours",
            "base": DURATION_BASE,
            "variant": DURATION_VARIANT,
            "cost_delta": 0.0,
            "increase_rate_pct": 0.0,
        },
        {
            "parameter": "log_multiplier",
            "base": LOG_MULTIPLIER_BASE,
            "variant": LOG_MULTIPLIER_VARIANT,
            "cost_delta": 0.0,
            "increase_rate_pct": 0.0,
        },
    ]
