from django.contrib import admin

from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')  
    can_delete = False
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'total_amount', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'order_number')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'customer_first_name', 'customer_last_name',
                       'delivery_location', 'delivery_town', 'delivery_county')
    inlines = [OrderItemInline]

    def total_amount(self, obj):
        return obj.total_amount()
    total_amount.short_description = 'Total Amount'
    def total_items(self, obj):
        return obj.total_items()
    total_items.short_description = 'Total Items'
    def vendors_summary(self, obj):
        summary = obj.vendors_summary()
        return ", ".join([f"{vendor.name}: {data['total_items']} items, ${data['total_sales']}" for vendor, data in summary.items()])
    vendors_summary.short_description = 'Vendors Summary'
    def get_customer_name(self, obj):
        return obj.get_customer_name()
    get_customer_name.short_description = 'Customer Name'
    def get_delivery_address(self, obj):
        return obj.get_delivery_address()   
    get_delivery_address.short_description = 'Delivery Address'
    list_display += ('total_items', 'vendors_summary', 'get_customer_name', 'get_delivery_address')