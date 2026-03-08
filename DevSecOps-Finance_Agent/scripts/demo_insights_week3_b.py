"""
3주차 (B) 데모: 입력 3종으로 engine 실행 후 insights(민감도, Trade-off, Top drivers) 변화 시연.

실행 (프로젝트 루트에서):
  python scripts/demo_insights_week3_b.py
  또는
  python -m scripts.demo_insights_week3_b
"""

import json
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
root = Path(__file__).resolve().parent.parent
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from src.engine import finance_run


def load_request(rel_path: str) -> dict:
    with open(root / rel_path, encoding="utf-8") as f:
        return json.load(f)


def run_demo():
    # 데모용 입력 3종 (시나리오/프로파일/트래픽 차이로 추천·민감도·트레이드오프 변화)
    requests_config = [
        ("samples/finance_request.sample.json", "기본 (S1, Standard)"),
        ("samples/demo_request_s3_lean.json", "S3 + LeanStartup"),
        ("samples/demo_request_high_traffic.json", "traffic_multiplier 2.0"),
    ]

    for rel_path, label in requests_config:
        path = root / rel_path
        if not path.exists():
            continue
        req = load_request(rel_path)

        print("=" * 60)
        print(f" [ {label} ]")
        print("=" * 60)
        result = finance_run(req)
        if "error" in result:
            print("Error:", result["error"])
            print()
            continue
        insights = result.get("insights", {})
        print("top_drivers:", json.dumps(insights.get("top_drivers", []), ensure_ascii=False, indent=2))
        print("sensitivity (요약):", [s["parameter"] + " " + str(s["increase_rate_pct"]) + "%" for s in insights.get("sensitivity", [])])
        print("tradeoffs:", insights.get("tradeoffs", []))
        print("cost_summary:", result.get("cost_summary", {}))
        print()

    print("데모 종료. 입력을 바꿔서 추천/민감도/Trade-off가 달라지는 것을 확인하세요.")


if __name__ == "__main__":
    run_demo()
