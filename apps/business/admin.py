from django.contrib import admin
from .models import Business, PaymentMethod, BusinessReview
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib import admin
from .models import Business, PaymentMethod, BusinessReview

@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'business_type', 'is_verified', 'verification_status', 'created_at')
    list_filter = ('business_type', 'is_verified', 'verification_status')
    search_fields = ('name', 'owner__email', 'business_reg_no', 'kra_pin')
    readonly_fields = ('created_at', 'updated_at', 'verified_at')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('verification_status', 'is_verified')
    fields = ('name', 'slug', 'owner', 'business_type', 'description', 'kra_pin', 
              'business_reg_no', 'is_verified', 'verification_status')

    def save_model(self, request, obj, form, change):
        try:
            obj.save()
        except Exception as e:
            self.message_user(request, f"Error saving business: {str(e)}", level='ERROR')

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('business', 'type', 'get_payment_details')
    list_filter = ('type', 'business')
    search_fields = ('business__name', 'till_number', 'business_number', 'bank_name')
    fields = ('business', 'type', 'till_number', 'business_number', 
             'paybill_account_number', 'bank_account_number', 
             'bank_name', 'card_number')
    
    def get_payment_details(self, obj):
        if obj.type == 'mpesa_till':
            return f"Till: {obj.till_number}"
        elif obj.type == 'mpesa_paybill':
            return f"Paybill: {obj.business_number}, Acc: {obj.paybill_account_number}"
        elif obj.type == 'bank_transfer':
            return f"Bank: {obj.bank_name}, Acc: {obj.bank_account_number}"
        elif obj.type == 'card':
            return f"Card: {obj.card_number}"
        return "-"
    get_payment_details.short_description = 'Payment Details'

    def save_model(self, request, obj, form, change):
        try:
            obj.full_clean()  # This will run model validation
            obj.save()
        except ValidationError as e:
            messages.error(request, str(e))
            return
        except Exception as e:
            messages.error(request, f"Error saving payment method: {str(e)}")
            return
        messages.success(request, 'Payment method saved successfully.')

@admin.register(BusinessReview)
class BusinessReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'orders_complete', 'orders_pending', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('product__name', 'user__email', 'comment')
    readonly_fields = ('created_at',)