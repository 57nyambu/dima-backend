BUSINESS_PERMISSIONS = {
    # Product permissions
    'PRODUCT_ADD': 'product.add',
    'PRODUCT_EDIT': 'product.edit',
    'PRODUCT_DELETE': 'product.delete',
    'PRODUCT_VIEW': 'product.view',
    'PRODUCT_MANAGE_INVENTORY': 'product.manage_inventory',
    
    # Order permissions
    'ORDER_VIEW': 'order.view',
    'ORDER_PROCESS': 'order.process',
    'ORDER_CANCEL': 'order.cancel',
    'ORDER_REFUND': 'order.refund',
    
    # Business permissions
    'BUSINESS_EDIT_PROFILE': 'business.edit_profile',
    'BUSINESS_MANAGE_TEAM': 'business.manage_team',
    'BUSINESS_MANAGE_SETTINGS': 'business.manage_settings',
    
    # Analytics permissions
    'ANALYTICS_VIEW_SALES': 'analytics.view_sales',
    'ANALYTICS_VIEW_CUSTOMERS': 'analytics.view_customers',
    
    # Financial permissions
    'FINANCIAL_VIEW_EARNINGS': 'financial.view_earnings',
    'FINANCIAL_REQUEST_PAYOUT': 'financial.request_payout',
}

PERMISSION_GROUPS = {
    'PRODUCT_MANAGEMENT': [
        'PRODUCT_ADD',
        'PRODUCT_EDIT',
        'PRODUCT_DELETE',
        'PRODUCT_VIEW',
        'PRODUCT_MANAGE_INVENTORY',
    ],
    'ORDER_MANAGEMENT': [
        'ORDER_VIEW',
        'ORDER_PROCESS',
        'ORDER_CANCEL',
        'ORDER_REFUND',
    ],
    'BUSINESS_OPERATIONS': [
        'BUSINESS_EDIT_PROFILE',
        'BUSINESS_MANAGE_TEAM',
        'BUSINESS_MANAGE_SETTINGS',
    ],
    'ANALYTICS_FINANCE': [
        'ANALYTICS_VIEW_SALES',
        'ANALYTICS_VIEW_CUSTOMERS',
        'FINANCIAL_VIEW_EARNINGS',
        'FINANCIAL_REQUEST_PAYOUT',
    ],
}