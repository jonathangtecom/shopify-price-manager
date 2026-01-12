"""
Tests for business rules (price calculation).
"""

import pytest
from datetime import datetime, timedelta
from app.processor.rules import (
    calculate_compare_at_price,
    calculate_markup,
    should_update_variant,
    SALES_LOOKBACK_DAYS,
    NEW_PRODUCT_DAYS
)


class TestCalculateCompareAtPrice:
    """Tests for calculate_compare_at_price function."""
    
    def test_recently_sold_product_gets_doubled_price(self):
        """Products sold in last 60 days should have compare_at = price * 2."""
        now = datetime.utcnow()
        product_id = "gid://shopify/Product/123"
        sold_products = {product_id}  # Product was sold
        
        result = calculate_compare_at_price(
            variant_price="29.99",
            product_id=product_id,
            product_created_at=now - timedelta(days=100),  # Old product
            sold_product_ids=sold_products,
            current_time=now
        )
        
        assert result == "59.98"
    
    def test_new_product_gets_doubled_price(self):
        """Products created in last 30 days should have compare_at = price * 2."""
        now = datetime.utcnow()
        product_id = "gid://shopify/Product/456"
        sold_products = set()  # Not sold
        
        result = calculate_compare_at_price(
            variant_price="15.00",
            product_id=product_id,
            product_created_at=now - timedelta(days=15),  # 15 days old
            sold_product_ids=sold_products,
            current_time=now
        )
        
        assert result == "30.00"
    
    def test_old_unsold_product_gets_price_cleared(self):
        """Products not sold in 60 days AND older than 30 days should have compare_at removed."""
        now = datetime.utcnow()
        product_id = "gid://shopify/Product/789"
        sold_products = set()  # Not sold
        
        result = calculate_compare_at_price(
            variant_price="50.00",
            product_id=product_id,
            product_created_at=now - timedelta(days=100),  # Old product
            sold_product_ids=sold_products,
            current_time=now
        )
        
        assert result is None
    
    def test_exactly_30_days_old_is_not_new(self):
        """Product exactly 30 days old should NOT be considered new."""
        now = datetime.utcnow()
        product_id = "gid://shopify/Product/101"
        sold_products = set()
        
        result = calculate_compare_at_price(
            variant_price="25.00",
            product_id=product_id,
            product_created_at=now - timedelta(days=NEW_PRODUCT_DAYS),  # Exactly 30 days
            sold_product_ids=sold_products,
            current_time=now
        )
        
        assert result is None
    
    def test_29_days_old_is_new(self):
        """Product 29 days old should be considered new."""
        now = datetime.utcnow()
        product_id = "gid://shopify/Product/102"
        sold_products = set()
        
        result = calculate_compare_at_price(
            variant_price="25.00",
            product_id=product_id,
            product_created_at=now - timedelta(days=29),
            sold_product_ids=sold_products,
            current_time=now
        )
        
        assert result == "50.00"
    
    def test_sold_takes_priority_over_age(self):
        """If product was sold, it should get price doubled regardless of age."""
        now = datetime.utcnow()
        product_id = "gid://shopify/Product/103"
        sold_products = {product_id}
        
        result = calculate_compare_at_price(
            variant_price="100.00",
            product_id=product_id,
            product_created_at=now - timedelta(days=365),  # Very old
            sold_product_ids=sold_products,
            current_time=now
        )
        
        assert result == "200.00"


class TestCalculateMarkup:
    """Tests for calculate_markup function."""
    
    def test_simple_price(self):
        assert calculate_markup("10.00") == "20.00"
    
    def test_price_with_cents(self):
        assert calculate_markup("29.99") == "59.98"
    
    def test_odd_cents_rounds_correctly(self):
        # 12.345 * 2 = 24.69 (rounded)
        assert calculate_markup("12.345") == "24.69"
    
    def test_whole_number_price(self):
        assert calculate_markup("50") == "100.00"


class TestShouldUpdateVariant:
    """Tests for should_update_variant function."""
    
    def test_both_none_no_update(self):
        assert should_update_variant(None, None) is False
    
    def test_current_none_new_value_update(self):
        assert should_update_variant(None, "59.98") is True
    
    def test_current_value_new_none_update(self):
        assert should_update_variant("59.98", None) is True
    
    def test_same_values_no_update(self):
        assert should_update_variant("59.98", "59.98") is False
    
    def test_different_values_update(self):
        assert should_update_variant("29.99", "59.98") is True
    
    def test_equivalent_values_no_update(self):
        # "60.00" and "60" should be considered equal
        assert should_update_variant("60.00", "60.00") is False
