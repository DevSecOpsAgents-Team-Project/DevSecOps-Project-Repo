# Finance Agent (A파트)

통제/스키마/재현성/정책버전/브레이크다운/해시를 담당하는 Finance Agent A파트입니다.  
XAI는 옵셔널 확장 필드로 설계되어 있으며, B파트 merge 시 스키마·엔진 충돌을 최소화합니다.

## 요구사항

- Python 3.10+
- **기본**: 외부 API 호출 없음 (가격은 로컬 `policy/` JSON, 설명은 템플릿만 사용)
- **선택**: `USE_AWS_PRICING_API=true` 시 AWS Pricing API 사용 → `pip install boto3` 필요
- **선택**: `USE_LLM_EXPLANATIONS=true` 시 LLM으로 설명 생성 → 구현 후 API 키 등 필요 (참고: `docs/DESIGN_LLM_AWS_PRICING.md`)

환경 변수 목록·예시: **`docs/ENV_VARS.md`**, **`env.example`** 참고.

## 설치

```bash
pip install -r requirements.txt
```

## 테스트

프로젝트 루트에서:

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

`.env` 파일을 두었다면 테스트 시 자동으로 로드됩니다. 자세한 방법: **`docs/HOW_TO_TEST_WITH_ENV.md`**

## 샘플 실행

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

## 디렉터리 구조

```
finance-agent/
  src/           # 엔진, 스키마 검증, 계약, 정책 로더, 가격 계산
  schemas/       # finance_request, finance_result JSON Schema
  policy/        # policy.v1.0.json 등 정책 파일
  samples/       # 샘플 요청
  tests/         # pytest
```

## 확장 (B파트 XAI)

- `engine.post_process_hook(result, request, context)` 가 no-op 확장 포인트로 존재합니다.
- B파트에서 이 hook을 오버라이드하거나, result에 `xai` 필드를 주입해도 `finance_result.schema.json`이 optional로 허용합니다.

## Explainability (3주차 B)

엔진 결과에 **insights** 가 포함됩니다. audit/재현/데모용으로 사용합니다.

- **top_drivers**: 비용 상위 3개 드라이버 (driver, cost, percentage).
- **sensitivity**: 파라미터별 비용 변화 — traffic_multiplier(1.0→2.0), duration_hours(24→168), log_multiplier(1.5→2.0) 에 대한 cost_delta, increase_rate_pct.
- **tradeoffs**: 조건부 문장 (S1 격리 제외, 규제 가중치 시 log_harden 우선, LeanStartup 비용 효율 등).

### 재현 방법

```bash
# 샘플 1개 실행
python -c "import json; from src.engine import finance_run; r=json.load(open('samples/finance_request.sample.json')); print(json.dumps(finance_run(r), indent=2, ensure_ascii=False))"

# 데모 (입력 3종으로 insights 변화 시연)
python scripts/demo_insights_week3_b.py
```

### 통제·감사 항목 (B 관련)

- 출력 형식/길이: `docs/OUTPUT_FORMAT_POLICY.md` 참고 (문장 최대 180자, 숫자 소수 2자리).
- insights 스키마: `schemas/finance_result.schema.json` 의 `insights` 필드.
