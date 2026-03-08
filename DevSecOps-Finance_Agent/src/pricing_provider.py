"""
Pricing 단가 소스 추상화.
- 기본: policy JSON (하드코딩)
- 선택: AWS Pricing API로 실제 단가 조회 (USE_AWS_PRICING_API=true)
"""

import os
from typing import Protocol


# 환경 변수: true면 AWS Pricing API 사용 시도
USE_AWS_PRICING_API_ENV = "USE_AWS_PRICING_API"


def _use_aws_pricing_api() -> bool:
    return os.environ.get(USE_AWS_PRICING_API_ENV, "").strip().lower() == "true"


class PricingProvider(Protocol):
    """단가 테이블을 제공하는 인터페이스. compute_costs()에 넘기는 pricing_table과 동일 형태."""

    def get_pricing_table(self, region: str, policy: dict) -> dict:
        """
        Returns:
            {"cloudwatch_per_gb": float, "s3_per_gb": float, "nat_egress_per_gb": float, "snapshot_per_gb": float}
        """
        ...


class PolicyPricingProvider:
    """기존 방식: policy JSON의 pricing_table 그대로 반환 (하드코딩)."""

    def get_pricing_table(self, region: str, policy: dict) -> dict:
        return dict(policy.get("pricing_table", {}))


class AwsPricingProvider:
    """
    AWS Pricing API로 단가 조회.
    boto3, pricing API 사용. 실패 시 policy fallback 또는 예외.
    """

    def get_pricing_table(self, region: str, policy: dict) -> dict:
        fallback = policy.get("pricing_table", {})
        try:
            return self._fetch_from_aws(region) or fallback
        except Exception:
            return fallback

    def _fetch_from_aws(self, region: str) -> dict | None:
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "USE_AWS_PRICING_API=true requires boto3. Install: pip install boto3"
            )
        # AWS Pricing API는 us-east-1에서만 제공
        client = boto3.client("pricing", region_name="us-east-1")
        out = {}
        # CloudWatch Logs: AmazonCloudWatch, product family 등으로 필터
        out["cloudwatch_per_gb"] = _get_cloudwatch_logs_price(client, region) or 0.50
        out["s3_per_gb"] = _get_s3_storage_price(client, region) or 0.023
        out["nat_egress_per_gb"] = _get_nat_egress_price(client, region) or 0.045
        out["snapshot_per_gb"] = _get_snapshot_price(client, region) or 0.05
        return out


def _get_cloudwatch_logs_price(client, region: str) -> float | None:
    # TODO: get_products(ServiceCode='AmazonCloudWatch', Filters=[location=region, ...])
    # 파싱 후 Data Transfer 또는 Ingestion 가격 반환. 없으면 None.
    return None


def _get_s3_storage_price(client, region: str) -> float | None:
    # TODO: get_products(ServiceCode='AmazonS3', ...)
    return None


def _get_nat_egress_price(client, region: str) -> float | None:
    # TODO: get_products(ServiceCode='AmazonVPC', productFamily='NAT Gateway', ...)
    return None


def _get_snapshot_price(client, region: str) -> float | None:
    # TODO: get_products(ServiceCode='AmazonEC2', productFamily='Storage Snapshot', ...)
    return None


def get_pricing_provider() -> PricingProvider:
    """환경 변수에 따라 사용할 PricingProvider 반환."""
    if _use_aws_pricing_api():
        return AwsPricingProvider()
    return PolicyPricingProvider()
