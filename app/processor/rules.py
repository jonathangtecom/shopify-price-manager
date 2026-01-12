"""
Business rules for calculating compare_at_price.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


# Rule constants
SALES_LOOKBACK_DAYS = 60
NEW_PRODUCT_DAYS = 30
PRICE_MULTIPLIER = Decimal("2")
MARKUP_MULTIPLIER = PRICE_MULTIPLIER  # Alias for consistency


@dataclass
class VariantUpdate:
    """Represents a variant price update to be applied."""

    product_id: str
    variant_id: str
    current_compare_at: Optional[str]
    new_compare_at: Optional[str]

    @property
    def needs_update(self) -> bool:
        """Check if this update needs to be applied."""
        return self.current_compare_at != self.new_compare_at

    @property
    def is_setting_price(self) -> bool:
        """Check if we're setting (not clearing) the price."""
        return self.new_compare_at is not None

    @property
    def is_clearing_price(self) -> bool:
        """Check if we're clearing the price."""
        return self.new_compare_at is None and self.current_compare_at is not None


def calculate_compare_at_price(
    variant_price: Optional[str],
    product_created_at: datetime,
    product_id: str,
    sold_product_ids: set[str],
    current_time: Optional[datetime] = None,
) -> Optional[str]:
    """
    Calculate the compare_at_price for a variant based on business rules.
    
    Rules:
    1. If product sold in last 60 days: compare_at_price = price × 2
    2. If product created in last 30 days: compare_at_price = price × 2
    3. Otherwise: compare_at_price = None (remove)
    
    Args:
        variant_price: Current price as string (e.g., "29.99")
        product_created_at: When the product was created
        product_id: Shopify product GID
        sold_product_ids: Set of product IDs that have been sold recently
        current_time: Current datetime (defaults to utcnow)
        
    Returns:
        New compare_at_price as string, or None to clear
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # Calculate cutoff dates
    sales_cutoff = current_time - timedelta(days=SALES_LOOKBACK_DAYS)
    new_product_cutoff = current_time - timedelta(days=NEW_PRODUCT_DAYS)

    # Determine if product qualifies for doubled price
    is_recently_sold = product_id in sold_product_ids
    is_new_product = product_created_at > new_product_cutoff

    if is_recently_sold or is_new_product:
        # Apply price × 2
        if variant_price is None:
            return None

        try:
            price = Decimal(variant_price)
            if price <= 0:
                return None

            doubled = (price * PRICE_MULTIPLIER).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            return str(doubled)
        except Exception:
            # Invalid price format
            return None
    else:
        # Clear compare_at_price
        return None


def evaluate_variant(
    variant: dict,
    product_id: str,
    product_created_at: datetime,
    sold_product_ids: set[str],
    current_time: Optional[datetime] = None,
) -> VariantUpdate:
    """
    Evaluate a variant and determine what update is needed.
    
    Args:
        variant: Variant dict with id, price, compare_at_price
        product_id: Parent product GID
        product_created_at: When product was created
        sold_product_ids: Set of recently sold product IDs
        current_time: Current datetime
        
    Returns:
        VariantUpdate describing the change (if any)
    """
    variant_id = variant["id"]
    current_price = variant.get("price")
    current_compare_at = variant.get("compare_at_price")

    new_compare_at = calculate_compare_at_price(
        variant_price=current_price,
        product_created_at=product_created_at,
        product_id=product_id,
        sold_product_ids=sold_product_ids,
        current_time=current_time,
    )

    return VariantUpdate(
        product_id=product_id,
        variant_id=variant_id,
        current_compare_at=current_compare_at,
        new_compare_at=new_compare_at,
    )


def calculate_markup(variant_price: Optional[str]) -> Optional[str]:
    """
    Calculate doubled price (price × 2).
    
    Args:
        variant_price: Current price as string (e.g., "29.99")
        
    Returns:
        Doubled price as string, or None if input invalid
    """
    if variant_price is None:
        return None
    
    try:
        price = Decimal(variant_price)
        if price <= 0:
            return None
        
        doubled = (price * PRICE_MULTIPLIER).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return str(doubled)
    except Exception:
        return None


def should_update_variant(
    current_compare_at: Optional[str],
    new_compare_at: Optional[str]
) -> bool:
    """
    Determine if a variant needs to be updated.
    
    Args:
        current_compare_at: Current compare_at_price value
        new_compare_at: Calculated new compare_at_price value
        
    Returns:
        True if update is needed, False otherwise
    """
    # Normalize values for comparison
    def normalize(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            decimal_value = Decimal(value)
            return str(decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        except Exception:
            return value
    
    current_normalized = normalize(current_compare_at)
    new_normalized = normalize(new_compare_at)
    
    return current_normalized != new_normalized


def format_price(value: Optional[str]) -> Optional[str]:
    """
    Format a price string to standard format (2 decimal places).
    
    Args:
        value: Price as string
        
    Returns:
        Formatted price or None
    """
    if value is None:
        return None
    
    try:
        decimal_value = Decimal(value)
        return str(decimal_value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except Exception:
        return None
