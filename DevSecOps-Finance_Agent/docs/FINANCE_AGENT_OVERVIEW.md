# Finance Agent 동작 요약 (로직 · 입출력 · 테스트 · XAI/LLM·AWS 위치)

기존 구현·스크립트 기준으로만 정리합니다.

---

## 1. 동작 로직 (엔진 흐름)

**진입점**: `src/engine.py` → `finance_run(request_obj: dict) -> dict`

흐름은 아래 8단계입니다.

| 단계 | 내용 | 사용 모듈 |
|------|------|-----------|
| 1 | **요청 스키마 검증** | `validate_request(request_obj)` → 실패 시 `error.type: SCHEMA_VALIDATION_ERROR` 반환 |
| 2 | **계약 검증** | `normalize_and_validate_assumptions(assumptions)` → 위반 시 `contract_error_response` (ASSUMPTION_CONTRACT_VIOLATION) |
| 3 | **정책 로드** | `load_policy(policy_version)` → `policy/policy.v1.0.json` 등 |
| 4 | **단가 결정 + 비용 계산** | `get_pricing_provider().get_pricing_table(region, policy)` → `compute_costs(resource_change, normalized, pricing_table)` |
| 5 | **스코어/추천** | `compute_action_scores(total, risk_adjusted_loss, profile)` → `recommended_action`, `decision_result` |
| 6 | **설명(insights) 생성** | `get_explanation_provider().generate_insights(...)` → 템플릿 또는 LLM |
| 7 | **결과 조립** | `result` dict 생성 후 `post_process_hook(result, request, context)` (기본 no-op) |
| 8 | **결과 스키마 검증** | `validate_result(result)` → 실패 시 `error.type: RESULT_SCHEMA_ERROR` |

- **단가**: `USE_AWS_PRICING_API` 미설정 → policy의 `pricing_table` 사용. `true` → `AwsPricingProvider`가 AWS Pricing API(또는 fallback)로 단가 조회.
- **설명**: `USE_LLM_EXPLANATIONS` 미설정 → 템플릿(`build_insights`). `true` → `LLMExplanationProvider`(현재 스텁, 구현 시 LLM 호출).

---

## 2. Input (요청)

**스키마**: `schemas/finance_request.schema.json`  
**샘플**: `samples/finance_request.sample.json`

필수 필드 요약:

```json
{
  "schema_version": "1.0",
  "incident_id": "문자열",
  "policy_version": "v1.0",
  "assumptions": {
    "duration_hours": 24,
    "traffic_multiplier": 1.0,
    "region": "ap-northeast-2",
    "service_tier": "S1",
    "org_profile": "Standard"
  },
  "resource_change": {
    "cloudwatch_log_gb_per_day": 10,
    "s3_storage_gb": 100,
    "nat_egress_gb": 5,
    "snapshot_gb": 20
  }
}
```

선택(엔진에서 참고): `risk_adjusted_loss`, `regulation_weight`, `severity` → 스코어·insights용.

---

## 3. Output (결과)

**스키마**: `schemas/finance_result.schema.json`

정상 시 `finance_run()`이 반환하는 dict 구조:

- `schema_version`, `incident_id`, `policy_version`
- `policy_meta`: `approved_by`, `approved_at`
- `assumption_hash`: 재현성용 해시
- `cost_summary`: `estimated_monthly_cost`, `currency`
- `driver_breakdown`: `[{ "driver", "cost", "percentage" }, ...]` (CloudWatchLogs, S3Storage, NAT_Egress, Snapshot)
- `top3_drivers`: 비용 상위 3개 드라이버 이름 배열
- **`insights`**: XAI/LLM이 채우는 설명 (아래 4번)

에러 시: `result["error"]` 존재, `type` / `message` 등.

---

## 4. LLM·XAI가 반환한 값이 나오는 위치

- **항상 나오는 곳**: **`result["insights"]`**
  - `insights` = `get_explanation_provider().generate_insights(...)` 반환값.
  - 템플릿 모드: `src/insights` (build_insights, sensitivity, tradeoff_engine)가 채움.
  - LLM 모드(`USE_LLM_EXPLANATIONS=true`): `LLMExplanationProvider`가 채움(현재는 스텁 → 구현 후 동일 키로 반환).

구조:

```text
result["insights"] = {
  "top_drivers": [ { "driver", "cost", "percentage" }, ... ],   // 상위 3개
  "sensitivity":  [ { "parameter", "base", "variant", "cost_delta", "increase_rate_pct" }, ... ],
  "tradeoffs":    [ "문장1", "문장2", ... ]
}
```

- **스키마에만 있는 optional 필드**: `result["xai"]`  
  - 엔진은 기본으로 `xai`를 설정하지 않음. `post_process_hook`에서 넣을 수 있고, 스키마는 `assumption_disclosure`, `top3_drivers`, `sensitivity`, `trade_off` 등 문자열 필드를 정의해 둔 상태.

**정리**: 지금 구현 기준으로 **설명(XAI/LLM) 결과는 전부 `result["insights"]`** 에서 보면 됩니다. 데모 스크립트도 여기만 출력합니다.

---

## 5. 핵심 Mock 데이터 테스트 방법 (기존 스크립트·테스트만)

### 5.1 pytest (mock = 샘플 요청 + 정책 파일)

프로젝트 루트에서:

```bash
python -m pytest tests/ -v
```

| 테스트 파일 | mock/검증 내용 |
|-------------|----------------|
| `test_schema_validation.py` | `samples/finance_request.sample.json`으로 요청 검증 + 엔진 결과 스키마 통과 |
| `test_insights.py` | fixture로 cost_breakdown, request, policy, pricing_result, decision_result 구성 → extract_top_drivers, compute_sensitivity, generate_tradeoffs, build_insights 동작 및 deterministic 검증 |
| `test_contract_reject.py` | duration_hours=12, region 오타 등 → 계약 위반 시 에러 반환 |
| `test_reproducibility.py` | 동일 요청 2회 → 동일 result dict |
| `test_policy_versioning.py` | fixture로 `policy.v1.1.json` 생성 후 v1.0 vs v1.1 요청 → 비용이 다르게 나오는지 검증 (이 테스트만 policy 단가 강제) |

Mock 데이터는 위 fixture와 `samples/finance_request.sample.json`이 전부입니다.

### 5.2 데모 스크립트 (입력 3종으로 insights 확인)

```bash
python scripts/demo_insights_week3_b.py
```

- **mock 입력**:  
  - `samples/finance_request.sample.json`  
  - `samples/demo_request_s3_lean.json`  
  - `samples/demo_request_high_traffic.json`  
- **출력**: 각 요청에 대해 `result["insights"]`(top_drivers, sensitivity 요약, tradeoffs)와 `cost_summary`를 콘솔에 출력.  
- **역할**: 입력만 바꿔서 **insights(XAI) 결과가 어디에 어떻게 나오는지** 확인용.

### 5.3 엔진 한 번 실행 (샘플 1개)

```bash
python -c "
import json
from src.engine import finance_run
with open('samples/finance_request.sample.json') as f:
    req = json.load(f)
result = finance_run(req)
print(json.dumps(result, indent=2, ensure_ascii=False))
"
```

- **mock**: `samples/finance_request.sample.json` 1개.  
- **확인**: 전체 result(비용·insights 포함)를 한 번에 보기.

---

## 6. AWS Pricing API가 잘 호출됐는지 확인 (새 스크립트 없이)

- **동작 방식**  
  - `USE_AWS_PRICING_API=true` 이면 `get_pricing_provider()`가 `AwsPricingProvider()`를 반환.  
  - `engine` 4단계에서 `get_pricing_provider().get_pricing_table(region, policy)`가 호출되고, 그 반환값으로 `compute_costs(...)`가 비용을 계산함.  
  - **실제 사용 단가는 result에 필드로 안 담김.**  
  - 따라서 “호출됐는지”는 **동작 경로**와 **비용 값 변화**로만 판단 가능합니다.

**기존 스크립트로 확인하는 방법**

1. **데모 스크립트로 비용 비교**  
   - `.env`에서 `USE_AWS_PRICING_API` 제거(또는 false) → `python scripts/demo_insights_week3_b.py` 실행 → `cost_summary` 값 기록.  
   - `.env`에 `USE_AWS_PRICING_API=true` (및 AWS 인증) 설정 후 같은 명령 다시 실행.  
   - **같은 샘플 요청인데 `cost_summary.estimated_monthly_cost`(또는 driver_breakdown)가 달라지면** AWS 경로(또는 AwsPricingProvider 기본값)가 적용된 것입니다. (지금 AWS 구현은 스텁이라, 실제 API를 붙이기 전에는 provider 기본 단가로만 차이가 날 수 있음.)

2. **엔진 한 번 실행**  
   - 위 5.3처럼 `finance_run(sample_request)` 한 번 돌린 뒤 `result["cost_summary"]`, `result["driver_breakdown"]`를 출력.  
   - `USE_AWS_PRICING_API=true` / `false` 두 번 실행해 두 결과를 비교하면, “단가 소스가 바뀌었는지” 간접 확인 가능.

3. **코드로 호출 경로 확인**  
   - `src/pricing_provider.py`: `_use_aws_pricing_api()`가 True면 `AwsPricingProvider` 사용.  
   - `src/engine.py` 82~85행: `get_pricing_provider().get_pricing_table(region, policy)` → `compute_costs(..., pricing_table)`.  
   - AWS 호출 실패 시 `AwsPricingProvider`는 policy의 `pricing_table`로 fallback하므로, **에러 없이 비용이 policy와 동일하면** “AWS는 시도했지만 fallback 사용”으로 해석할 수 있습니다.

**정리**: 새 스크립트 없이, **기존 데모 스크립트·엔진 1회 실행**으로 `cost_summary`/`driver_breakdown`를 비교하고, `pricing_provider`/`engine` 코드 흐름으로 “AWS Pricing API가 쓰인 경로인지” 확인하면 됩니다.

---

## 7. 한 줄 요약

- **로직**: `engine.finance_run` → 요청 검증 → 계약 검증 → 정책 로드 → 단가(policy 또는 AWS) → 비용 계산 → 스코어/추천 → insights(템플릿 또는 LLM) → result 반환.  
- **Input**: `schemas/finance_request.schema.json` / `samples/finance_request.sample.json` 구조.  
- **Output**: `schemas/finance_result.schema.json` 구조, 설명은 **`result["insights"]`**.  
- **Mock 테스트**: `pytest tests/` + `scripts/demo_insights_week3_b.py` + 엔진 1회 실행으로 충분.  
- **XAI/LLM 결과 위치**: **`result["insights"]`** (top_drivers, sensitivity, tradeoffs).  
- **AWS Pricing API 사용 여부**: 같은 요청으로 `USE_AWS_PRICING_API` on/off 시 `cost_summary`/`driver_breakdown` 비교 및 `pricing_provider`·`engine` 코드 흐름으로 확인.
