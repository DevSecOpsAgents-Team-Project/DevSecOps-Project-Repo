"""
Pricing 단가 소스 추상화.
- 기본: policy JSON (하드코딩)
- 선택: AWS Pricing API로 실제 단가 조회 (USE_AWS_PRICING_API=true)
"""

import json
import os
from typing import Any, Protocol


# 환경 변수: true면 AWS Pricing API 사용 시도
USE_AWS_PRICING_API_ENV = "USE_AWS_PRICING_API"

# 리전 코드 → AWS Pricing location 값 (get_products Filter용)
_AWS_REGION_TO_LOCATION: dict[str, str] = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-2": "US West (Oregon)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "eu-west-1": "EU (Ireland)",
    "eu-central-1": "EU (Frankfurt)",
}


def _use_aws_pricing_api() -> bool:
    return os.environ.get(USE_AWS_PRICING_API_ENV, "").strip().lower() == "true"


def _aws_location(region: str) -> str:
    return _AWS_REGION_TO_LOCATION.get(region, "US East (N. Virginia)")


def _parse_ondemand_usd(price_list_item: str) -> float | None:
    """get_products PriceList 항목(JSON 문자열)에서 OnDemand USD 단가 추출."""
    try:
        data = json.loads(price_list_item)
        terms = data.get("terms") or {}
        ondemand = terms.get("OnDemand") or {}
        if not ondemand:
            return None
        first_sku = next(iter(ondemand.values()))
        dims = first_sku.get("priceDimensions") or {}
        if not dims:
            return None
        first_dim = next(iter(dims.values()))
        usd = (first_dim.get("pricePerUnit") or {}).get("USD")
        if usd is None:
            return None
        return float(usd)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def _fetch_first_price(
    client: Any,
    service_code: str,
    filters: list[dict],
) -> float | None:
    """get_products 호출 후 첫 번째 상품의 OnDemand USD 가격 반환."""
    try:
        resp = client.get_products(
            ServiceCode=service_code,
            Filters=filters,
            FormatVersion="aws_v1",
            MaxResults=1,
        )
        for item in (resp.get("PriceList") or []):
            price = _parse_ondemand_usd(item)
            if price is not None:
                return round(price, 4)
    except Exception:
        pass
    return None


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
    boto3 get_products 호출. 실패 시 policy fallback.
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
        client = boto3.client("pricing", region_name="us-east-1")
        location = _aws_location(region)
        out = {}
        out["cloudwatch_per_gb"] = _get_cloudwatch_logs_price(client, location) or 0.50
        out["s3_per_gb"] = _get_s3_storage_price(client, location) or 0.023
        out["nat_egress_per_gb"] = _get_nat_egress_price(client, location) or 0.045
        out["snapshot_per_gb"] = _get_snapshot_price(client, location) or 0.05
        return out


def _get_cloudwatch_logs_price(client: Any, location: str) -> float | None:
    """CloudWatch Logs 단가 (USD/GB). get_products 직접 호출."""
    return _fetch_first_price(
        client,
        "AmazonCloudWatch",
        [
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Data Transfer"},
        ],
    )


def _get_s3_storage_price(client: Any, location: str) -> float | None:
    """S3 스토리지 단가 (USD/GB). get_products 직접 호출."""
    return _fetch_first_price(
        client,
        "AmazonS3",
        [
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage"},
        ],
    )


def _get_nat_egress_price(client: Any, location: str) -> float | None:
    """NAT Gateway 데이터처리 단가 (USD/GB). get_products 직접 호출."""
    return _fetch_first_price(
        client,
        "AmazonEC2",
        [
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "NAT Gateway"},
        ],
    )


def _get_snapshot_price(client: Any, location: str) -> float | None:
    """EBS 스냅샷 스토리지 단가 (USD/GB). get_products 직접 호출."""
    return _fetch_first_price(
        client,
        "AmazonEC2",
        [
            {"Type": "TERM_MATCH", "Field": "location", "Value": location},
            {"Type": "TERM_MATCH", "Field": "productFamily", "Value": "Storage Snapshot"},
        ],
    )


def get_pricing_provider() -> PricingProvider:
    """환경 변수에 따라 사용할 PricingProvider 반환."""
    if _use_aws_pricing_api():
        return AwsPricingProvider()
    return PolicyPricingProvider()
