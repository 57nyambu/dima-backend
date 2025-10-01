from django.core.cache import cache
from django.conf import settings as django_settings
from typing import Optional
from .models import MarketplaceSettings

class MarketplaceSettingsManager:
    """Centralized manager for marketplace settings"""
    
    CACHE_KEY = 'marketplace_settings'
    CACHE_TIMEOUT = 3600  # 1 hour
    
    @classmethod
    def get_settings(cls) -> MarketplaceSettings:
        """Get marketplace settings with caching"""
        settings = cache.get(cls.CACHE_KEY)
        
        if not settings:
            settings = MarketplaceSettings.objects.first()
            if not settings:
                settings = MarketplaceSettings.objects.create()
            cache.set(cls.CACHE_KEY, settings, cls.CACHE_TIMEOUT)
        
        return settings
    
    @classmethod
    def clear_cache(cls):
        """Clear settings cache"""
        cache.delete(cls.CACHE_KEY)
    
    @classmethod
    def get_commission_rate(cls) -> float:
        """Get current commission rate as decimal"""
        return float(cls.get_settings().commission_rate) / 100
    
    @classmethod
    def get_currency(cls) -> str:
        """Get current currency code"""
        return cls.get_settings().currency
    
    @classmethod
    def get_min_order_amount(cls) -> float:
        """Get minimum order amount"""
        return float(cls.get_settings().min_order_amount)
    
    @classmethod
    def get_feature_flags(cls) -> dict:
        """Get all feature flags"""
        settings = cls.get_settings()
        return {
            'reviews_enabled': settings.enable_reviews,
            'wishlist_enabled': settings.enable_wishlist,
            'comparison_enabled': settings.enable_comparison,
            'vendor_chat_enabled': settings.enable_vendor_chat
        }
    
    @classmethod
    def validate_order_amount(cls, amount: float) -> bool:
        """Validate if order amount meets minimum requirement"""
        return amount >= cls.get_min_order_amount()
    
    @classmethod
    def validate_cart_quantity(cls, quantity: int) -> bool:
        """Validate if cart quantity meets maximum limit"""
        return quantity <= cls.get_settings().max_products_per_order
