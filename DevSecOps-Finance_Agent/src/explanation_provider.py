"""
설명(insights) 생성 소스 추상화.
- 기본: 템플릿 기반 (하드코딩, deterministic)
- 선택: LLM으로 문장 생성 (USE_LLM_EXPLANATIONS=true) — OpenAI API 직접 호출
"""

import json
import os
from typing import Protocol

# 환경 변수: true면 LLM 사용 시도
USE_LLM_EXPLANATIONS_ENV = "USE_LLM_EXPLANATIONS"
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"


def _use_llm_explanations() -> bool:
    return os.environ.get(USE_LLM_EXPLANATIONS_ENV, "").strip().lower() == "true"


class ExplanationProvider(Protocol):
    """insights dict 생성. 반환 형태: { "top_drivers": [...], "sensitivity": [...], "tradeoffs": [...] }"""

    def generate_insights(
        self,
        request: dict,
        pricing_result: dict,
        decision_result: dict,
        policy: dict,
        normalized_assumptions: dict,
    ) -> dict:
        ...


class TemplateExplanationProvider:
    """기존 방식: build_insights (템플릿만 사용, LLM 없음)."""

    def generate_insights(
        self,
        request: dict,
        pricing_result: dict,
        decision_result: dict,
        policy: dict,
        normalized_assumptions: dict,
    ) -> dict:
        from .insights import build_insights
        return build_insights(
            request,
            pricing_result,
            decision_result,
            policy,
            normalized_assumptions,
        )


class LLMExplanationProvider:
    """
    LLM으로 설명 생성. OpenAI API 직접 호출.
    비용 결과·컨텍스트를 프롬프트에 넣고, 응답을 insights 구조로 파싱.
    실패 시 TemplateExplanationProvider로 fallback 가능.
    """

    def __init__(self, fallback_to_template: bool = True):
        self._fallback = fallback_to_template
        self._template = TemplateExplanationProvider()

    def generate_insights(
        self,
        request: dict,
        pricing_result: dict,
        decision_result: dict,
        policy: dict,
        normalized_assumptions: dict,
    ) -> dict:
        try:
            return self._call_llm(
                request, pricing_result, decision_result, policy, normalized_assumptions
            )
        except Exception:
            if self._fallback:
                return self._template.generate_insights(
                    request, pricing_result, decision_result, policy, normalized_assumptions
                )
            raise

    def _call_llm(
        self,
        request: dict,
        pricing_result: dict,
        decision_result: dict,
        policy: dict,
        normalized_assumptions: dict,
    ) -> dict:
        api_key = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
        if not api_key:
            raise RuntimeError(
                "USE_LLM_EXPLANATIONS=true requires OPENAI_API_KEY in environment."
            )

        prompt = _build_prompt(request, pricing_result, decision_result, normalized_assumptions)
        response_text = _openai_chat(api_key, prompt)
        return _parse_insights_response(response_text, pricing_result)


def _openai_chat(api_key: str, prompt: str) -> str:
    """OpenAI Chat Completions API 호출 후 assistant 메시지 내용 반환."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("USE_LLM_EXPLANATIONS=true requires openai. Install: pip install openai")
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )
    msg = resp.choices[0].message
    return (msg.content or "").strip()


def _build_prompt(
    request: dict,
    pricing_result: dict,
    decision_result: dict,
    normalized_assumptions: dict,
) -> str:
    """비용·컨텍스트를 요약한 프롬프트 문자열 생성."""
    total = pricing_result.get("total", 0)
    breakdown = pricing_result.get("breakdown", [])
    top3 = pricing_result.get("top3_drivers", [])
    rec = decision_result.get("recommended_action", "")
    profile = decision_result.get("profile", "")
    service_tier = decision_result.get("service_tier", "")
    reg_weight = decision_result.get("regulation_weight", 1.0)

    parts = [
        "You are a finance agent. Based on the following cost and context, output a JSON object only (no markdown, no code block).",
        "",
        "Context:",
        f"- Total estimated cost: {total} USD",
        f"- Driver breakdown: {breakdown}",
        f"- Top 3 drivers: {top3}",
        f"- Recommended action: {rec}",
        f"- Profile: {profile}, Service tier: {service_tier}, Regulation weight: {reg_weight}",
        "",
        "Output JSON with exactly these keys:",
        '- "top_drivers": array of 3 objects, each with "driver" (string), "cost" (number), "percentage" (number), from the breakdown above.',
        '- "sensitivity": array of 3 objects, each with "parameter" (string), "base" (number), "variant" (number), "cost_delta" (number), "increase_rate_pct" (number). Use placeholders e.g. traffic_multiplier 1.0/2.0, duration_hours 24/168, log_multiplier 1.5/2.0 with 0 or small numbers if unknown.',
        '- "tradeoffs": array of short strings (1-3 sentences) explaining trade-offs and recommendations for the user in Korean.',
        "",
        "Return only the JSON object, no other text.",
    ]
    return "\n".join(parts)


def _parse_insights_response(response_text: str, pricing_result: dict) -> dict:
    """LLM 응답 문자열을 파싱해 insights 구조로 반환. 형식 오류 시 예외."""
    text = response_text
    if "```" in text:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            text = text[start:end]
    data = json.loads(text)
    top_drivers = data.get("top_drivers")
    sensitivity = data.get("sensitivity")
    tradeoffs = data.get("tradeoffs")
    if not (isinstance(top_drivers, list) and isinstance(sensitivity, list) and isinstance(tradeoffs, list)):
        raise ValueError("LLM response missing top_drivers, sensitivity, or tradeoffs")
    return {
        "top_drivers": top_drivers[:3],
        "sensitivity": sensitivity[:3],
        "tradeoffs": [str(s) for s in tradeoffs[:10]],
    }


def get_explanation_provider() -> ExplanationProvider:
    """환경 변수에 따라 사용할 ExplanationProvider 반환."""
    if _use_llm_explanations():
        return LLMExplanationProvider(fallback_to_template=True)
    return TemplateExplanationProvider()
