"""
Week3 explainability 모듈 테스트.

- extract_top_drivers: deterministic, top3 정렬, percentage 계산
- compute_sensitivity: deterministic, delta/증가율 계산
- generate_tradeoffs: deterministic, 조건별 문장 트리거
- build_insights: deterministic, 구조(top_drivers, sensitivity, tradeoffs) 유지
"""

import pytest

from src.insights.insight_builder import extract_top_drivers, build_insights
from src.insights.sensitivity import compute_sensitivity
from src.insights.tradeoff_engine import generate_tradeoffs


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cost_breakdown_four_drivers():
    """비용이 서로 다른 4개 드라이버. 총합 86.84."""
    return {
        "CloudWatchLogs": 43.21,
        "S3Storage": 22.11,
        "NAT_Egress": 17.32,
        "Snapshot": 4.2,
    }


@pytest.fixture
def cost_breakdown_three_only():
    """드라이버 3개만 있는 경우."""
    return {
        "CloudWatchLogs": 10.0,
        "S3Storage": 20.0,
        "NAT_Egress": 30.0,
    }


@pytest.fixture
def cost_breakdown_zero_total():
    """총 비용 0 (percentage 0.0)."""
    return {
        "A": 0.0,
        "B": 0.0,
        "C": 0.0,
    }


@pytest.fixture
def policy_with_pricing():
    """compute_sensitivity / build_insights용 최소 정책."""
    return {
        "pricing_table": {
            "cloudwatch_per_gb": 0.50,
            "s3_per_gb": 0.023,
            "nat_egress_per_gb": 0.045,
            "snapshot_per_gb": 0.05,
        },
    }


@pytest.fixture
def normalized_assumptions():
    """계약 통과 가정 (pricing 호출에 필요)."""
    return {
        "duration_hours": 24,
        "traffic_multiplier": 1.0,
        "region": "ap-northeast-2",
        "service_tier": "S2",
        "org_profile": "Standard",
    }


@pytest.fixture
def resource_change():
    """요청용 resource_change."""
    return {
        "cloudwatch_log_gb_per_day": 10,
        "s3_storage_gb": 100,
        "nat_egress_gb": 5,
        "snapshot_gb": 20,
    }


@pytest.fixture
def request_with_resource(resource_change):
    """resource_change를 담은 요청 (compute_sensitivity / build_insights용)."""
    return {"resource_change": resource_change}


# ---------------------------------------------------------------------------
# extract_top_drivers
# ---------------------------------------------------------------------------

class TestExtractTopDrivers:
    """extract_top_drivers() 테스트."""

    def test_deterministic_same_input_same_output(self, cost_breakdown_four_drivers):
        """동일 입력에 대해 여러 번 호출 시 항상 동일한 결과."""
        first = extract_top_drivers(cost_breakdown_four_drivers)
        second = extract_top_drivers(cost_breakdown_four_drivers)
        assert first == second

    def test_returns_at_most_three(self, cost_breakdown_four_drivers):
        """항상 최대 3개만 반환."""
        result = extract_top_drivers(cost_breakdown_four_drivers)
        assert len(result) <= 3
        assert len(result) == 3

    def test_sorted_by_cost_descending(self, cost_breakdown_four_drivers):
        """비용 기준 내림차순 정렬."""
        result = extract_top_drivers(cost_breakdown_four_drivers)
        costs = [r["cost"] for r in result]
        assert costs == sorted(costs, reverse=True)
        assert result[0]["driver"] == "CloudWatchLogs"
        assert result[0]["cost"] == 43.21
        assert result[1]["driver"] == "S3Storage"
        assert result[2]["driver"] == "NAT_Egress"

    def test_percentage_sum_bounded(self, cost_breakdown_four_drivers):
        """상위 3개 percentage 합은 0~100. (전체 4개 중 3개만 쓰므로 100 미만일 수 있음.)"""
        result = extract_top_drivers(cost_breakdown_four_drivers)
        total_pct = sum(r["percentage"] for r in result)
        assert 0 <= total_pct <= 101.0  # 반올림으로 100 초과 가능

    def test_percentage_calculation_accuracy(self, cost_breakdown_four_drivers):
        """percentage = (cost / total) * 100, 소수 2자리."""
        total = sum(cost_breakdown_four_drivers.values())
        result = extract_top_drivers(cost_breakdown_four_drivers)
        for item in result:
            expected_pct = round(item["cost"] / total * 100, 2)
            assert item["percentage"] == expected_pct

    def test_three_drivers_only_returns_three(self, cost_breakdown_three_only):
        """드라이버가 3개일 때 3개 그대로 반환."""
        result = extract_top_drivers(cost_breakdown_three_only)
        assert len(result) == 3
        total_pct = sum(r["percentage"] for r in result)
        assert abs(total_pct - 100.0) < 0.01

    def test_zero_total_percentage_all_zero(self, cost_breakdown_zero_total):
        """총 비용 0이면 percentage는 0.0."""
        result = extract_top_drivers(cost_breakdown_zero_total)
        for item in result:
            assert item["percentage"] == 0.0

    def test_empty_input_returns_empty_list(self):
        """빈 dict 입력 시 빈 리스트."""
        assert extract_top_drivers({}) == []

    def test_does_not_mutate_input(self, cost_breakdown_four_drivers):
        """입력 dict를 수정하지 않음."""
        original = dict(cost_breakdown_four_drivers)
        extract_top_drivers(cost_breakdown_four_drivers)
        assert cost_breakdown_four_drivers == original


# ---------------------------------------------------------------------------
# compute_sensitivity
# ---------------------------------------------------------------------------

class TestComputeSensitivity:
    """compute_sensitivity() 테스트."""

    def test_deterministic_same_input_same_output(
        self, request_with_resource, policy_with_pricing, normalized_assumptions
    ):
        """동일 입력 시 항상 동일 sensitivity 리스트."""
        req = request_with_resource
        policy = policy_with_pricing
        norm = normalized_assumptions
        base = 50.0
        first = compute_sensitivity(req, policy, norm, base)
        second = compute_sensitivity(req, policy, norm, base)
        assert first == second

    def test_returns_three_scenarios(
        self, request_with_resource, policy_with_pricing, normalized_assumptions
    ):
        """항상 3개 시나리오 반환 (traffic, duration, log)."""
        result = compute_sensitivity(
            request_with_resource,
            policy_with_pricing,
            normalized_assumptions,
            base_total=50.0,
        )
        assert len(result) == 3
        params = [r["parameter"] for r in result]
        assert params == ["traffic_multiplier", "duration_hours", "log_multiplier"]

    def test_sensitivity_delta_formula(
        self, request_with_resource, policy_with_pricing, normalized_assumptions
    ):
        """cost_delta = variant_total - base_total, increase_rate_pct = (delta/base)*100."""
        base_total = 40.0
        result = compute_sensitivity(
            request_with_resource,
            policy_with_pricing,
            normalized_assumptions,
            base_total=base_total,
        )
        for row in result:
            delta = row["cost_delta"]
            rate = row["increase_rate_pct"]
            if base_total != 0:
                expected_rate = round((delta / base_total) * 100, 2)
                assert rate == expected_rate

    def test_traffic_multiplier_increases_cost(
        self, request_with_resource, policy_with_pricing, normalized_assumptions
    ):
        """traffic_multiplier 1.0→2.0 시 비용 증가 → cost_delta >= 0."""
        from src.pricing import compute_costs

        rc = request_with_resource["resource_change"]
        pt = policy_with_pricing["pricing_table"]
        base_total = compute_costs(rc, normalized_assumptions, pt)["total"]
        result = compute_sensitivity(
            request_with_resource,
            policy_with_pricing,
            normalized_assumptions,
            base_total=base_total,
        )
        traffic_row = next(r for r in result if r["parameter"] == "traffic_multiplier")
        assert traffic_row["cost_delta"] >= 0
        assert traffic_row["base"] == 1.0
        assert traffic_row["variant"] == 2.0

    def test_empty_pricing_table_returns_zero_deltas(self, request_with_resource, normalized_assumptions):
        """pricing_table 없으면 cost_delta, increase_rate_pct 0."""
        policy_empty = {}
        result = compute_sensitivity(
            request_with_resource,
            policy_empty,
            normalized_assumptions,
            base_total=10.0,
        )
        assert len(result) == 3
        for row in result:
            assert row["cost_delta"] == 0.0
            assert row["increase_rate_pct"] == 0.0

    def test_does_not_mutate_inputs(
        self, request_with_resource, policy_with_pricing, normalized_assumptions
    ):
        """request, policy, normalized를 수정하지 않음."""
        req = dict(request_with_resource)
        policy = dict(policy_with_pricing)
        norm = dict(normalized_assumptions)
        compute_sensitivity(req, policy, norm, 50.0)
        assert req == request_with_resource
        assert norm == normalized_assumptions


# ---------------------------------------------------------------------------
# generate_tradeoffs
# ---------------------------------------------------------------------------

class TestGenerateTradeoffs:
    """generate_tradeoffs() 테스트."""

    def test_deterministic_same_input_same_output(self):
        """동일 context에 대해 항상 동일 문장 리스트."""
        ctx = {"service_tier": "S1", "recommended_action": "isolate", "profile": "Standard"}
        first = generate_tradeoffs(ctx)
        second = generate_tradeoffs(ctx)
        assert first == second

    def test_condition_s1_and_isolate_triggers_sentence(self):
        """service_tier S1 이고 recommended_action isolate → 격리 제외 문장."""
        ctx = {"service_tier": "S1", "recommended_action": "isolate"}
        result = generate_tradeoffs(ctx)
        assert any("격리" in s and "제외" in s for s in result)
        assert any("S1" in s for s in result)

    def test_condition_s1_without_isolate_no_s1_sentence(self):
        """S1이지만 isolate가 아니면 격리 제외 문장 없음."""
        ctx = {"service_tier": "S1", "recommended_action": "log_harden"}
        result = generate_tradeoffs(ctx)
        assert not any("격리" in s and "제외" in s for s in result)

    def test_condition_regulation_weight_high_triggers_log_sentence(self):
        """regulation_weight >= 1.5 → 로그 강화 우선 문장."""
        ctx = {"regulation_weight": 1.5, "profile": "Standard"}
        result = generate_tradeoffs(ctx)
        assert any("로그 강화" in s or "log_harden" in s for s in result)

    def test_condition_regulation_weight_low_no_log_sentence(self):
        """regulation_weight < 1.5 → 로그 강화 문장 없음."""
        ctx = {"regulation_weight": 1.0, "profile": "Standard"}
        result = generate_tradeoffs(ctx)
        assert not any("log_harden" in s for s in result)

    def test_condition_lean_startup_triggers_sentence(self):
        """profile LeanStartup → 비용 효율성 문장."""
        ctx = {"profile": "LeanStartup"}
        result = generate_tradeoffs(ctx)
        assert any("LeanStartup" in s and "비용" in s for s in result)

    def test_all_conditions_trigger_three_sentences(self):
        """세 조건 모두 만족 시 문장 3개."""
        ctx = {
            "service_tier": "S1",
            "recommended_action": "isolate",
            "regulation_weight": 2.0,
            "profile": "LeanStartup",
        }
        result = generate_tradeoffs(ctx)
        assert len(result) == 3

    def test_empty_context_returns_empty_list(self):
        """조건 없으면 빈 리스트."""
        result = generate_tradeoffs({})
        assert result == []

    def test_does_not_mutate_context(self):
        """context dict 수정하지 않음."""
        ctx = {"profile": "LeanStartup"}
        original = dict(ctx)
        generate_tradeoffs(ctx)
        assert ctx == original


# ---------------------------------------------------------------------------
# build_insights
# ---------------------------------------------------------------------------

class TestBuildInsights:
    """build_insights() 테스트."""

    @pytest.fixture
    def pricing_result(self, cost_breakdown_four_drivers):
        """build_insights용 pricing 결과. total + breakdown."""
        total = sum(cost_breakdown_four_drivers.values())
        breakdown = [
            {"driver": k, "cost": v, "percentage": round(v / total * 100, 2)}
            for k, v in sorted(
                cost_breakdown_four_drivers.items(), key=lambda x: x[1], reverse=True
            )
        ]
        return {
            "total": total,
            "breakdown": breakdown,
            "top3_drivers": [b["driver"] for b in breakdown[:3]],
        }

    @pytest.fixture
    def decision_result(self):
        """build_insights용 decision_result."""
        return {
            "recommended_action": "log_harden",
            "profile": "Standard",
            "regulation_weight": 1.0,
            "service_tier": "S2",
            "severity": "medium",
        }

    def test_deterministic_same_input_same_output(
        self,
        request_with_resource,
        pricing_result,
        decision_result,
        policy_with_pricing,
        normalized_assumptions,
    ):
        """동일 입력 시 build_insights 결과 동일."""
        req = request_with_resource
        first = build_insights(req, pricing_result, decision_result, policy_with_pricing, normalized_assumptions)
        second = build_insights(req, pricing_result, decision_result, policy_with_pricing, normalized_assumptions)
        assert first == second

    def test_structure_has_required_keys(
        self,
        request_with_resource,
        pricing_result,
        decision_result,
        policy_with_pricing,
        normalized_assumptions,
    ):
        """반환 dict에 top_drivers, sensitivity, tradeoffs 필수 키 존재."""
        result = build_insights(
            request_with_resource,
            pricing_result,
            decision_result,
            policy_with_pricing,
            normalized_assumptions,
        )
        assert "top_drivers" in result
        assert "sensitivity" in result
        assert "tradeoffs" in result
        assert isinstance(result["top_drivers"], list)
        assert isinstance(result["sensitivity"], list)
        assert isinstance(result["tradeoffs"], list)

    def test_top_drivers_from_pricing_breakdown(
        self,
        request_with_resource,
        pricing_result,
        decision_result,
        policy_with_pricing,
        normalized_assumptions,
    ):
        """top_drivers는 pricing_result breakdown 기반 상위 3개."""
        result = build_insights(
            request_with_resource,
            pricing_result,
            decision_result,
            policy_with_pricing,
            normalized_assumptions,
        )
        assert len(result["top_drivers"]) <= 3
        for item in result["top_drivers"]:
            assert "driver" in item and "cost" in item and "percentage" in item

    def test_sensitivity_has_three_rows(
        self,
        request_with_resource,
        pricing_result,
        decision_result,
        policy_with_pricing,
        normalized_assumptions,
    ):
        """sensitivity는 항상 3개 시나리오."""
        result = build_insights(
            request_with_resource,
            pricing_result,
            decision_result,
            policy_with_pricing,
            normalized_assumptions,
        )
        assert len(result["sensitivity"]) == 3
        params = {r["parameter"] for r in result["sensitivity"]}
        assert params == {"traffic_multiplier", "duration_hours", "log_multiplier"}

    def test_tradeoffs_list_of_strings(
        self,
        request_with_resource,
        pricing_result,
        decision_result,
        policy_with_pricing,
        normalized_assumptions,
    ):
        """tradeoffs는 문자열 리스트."""
        result = build_insights(
            request_with_resource,
            pricing_result,
            decision_result,
            policy_with_pricing,
            normalized_assumptions,
        )
        assert all(isinstance(s, str) for s in result["tradeoffs"])
