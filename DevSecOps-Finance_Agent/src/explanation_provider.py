"""
설명(insights) 생성 소스 추상화.
- 기본: 템플릿 기반 (하드코딩, deterministic)
- 선택: LLM으로 문장 생성 (USE_LLM_EXPLANATIONS=true)
"""

import os
from typing import Protocol

# 환경 변수: true면 LLM 사용 시도
USE_LLM_EXPLANATIONS_ENV = "USE_LLM_EXPLANATIONS"


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
    LLM으로 설명 생성.
    OpenAI/Anthropic 등 호출 후 응답을 insights 구조로 파싱.
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
        # TODO: 실제 LLM 호출 구현
        # 1) request, pricing_result, decision_result 요약을 프롬프트로 구성
        # 2) OpenAI/Anthropic 등 API 호출 (API 키는 환경 변수 등에서 로드)
        # 3) 응답을 파싱해 {"top_drivers": [...], "sensitivity": [...], "tradeoffs": [...]} 형태로 반환
        # 예: openai.ChatCompletion.create(...) 후 JSON 파싱
        raise NotImplementedError(
            "LLM explanation not implemented. Set OPENAI_API_KEY (or similar) and implement "
            "_call_llm() in explanation_provider.LLMExplanationProvider, or use template: "
            "USE_LLM_EXPLANATIONS=false"
        )


def get_explanation_provider() -> ExplanationProvider:
    """환경 변수에 따라 사용할 ExplanationProvider 반환."""
    if _use_llm_explanations():
        return LLMExplanationProvider(fallback_to_template=True)
    return TemplateExplanationProvider()
