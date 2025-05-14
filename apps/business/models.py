from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from apps.accounts.models import CustomUser
from django.utils.text import slugify
from django.core.exceptions import ValidationError

class Business(models.Model):
    CATEGORY_TYPE = [
            ('fashion', 'Fashion & Clothing'),
            ('electronics', 'Electronics'),
            ('agriculture', 'Agriculture & Farm Produce'),
            ('food', 'Food & Groceries'),
            ('health', 'Health & Pharmacy'),
            ('logistics', 'Logistics & Transport Services'),
            ('enterteinment', 'Enterteinment & Events'),
            ('manufacture', 'Manufacture & Processing'),
            ('sme', 'Small/Medium Enterprise'),
            ('second-hand', 'SecondHand Dealer'),
            ('others', 'Others')
    ]
    VERIFICATION_STATUS = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='businesses')
    name = models.CharField(max_length=225)
    slug = models.SlugField(unique=True)
    business_type = models.CharField(max_length=30, choices=CATEGORY_TYPE)
    description = models.CharField(max_length=225, blank=True)
    kra_pin = models.CharField(max_length=30, blank=True)
    business_reg_no = models.CharField(max_length=30, blank=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    verification_status = models.CharField(
        max_length=10, choices=VERIFICATION_STATUS, default='pending'
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Businesses"
        indexes = [models.Index(fields=['owner'])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.owner} - {self.name} - ({self.get_business_type_display()})"


class PaymentMethods(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('mpesa_till', 'M-Pesa Till'),
        ('mpesa_paybill', 'M-Pesa Paybill'),
        ('mpesa_send_money', 'M-Pesa Send Money'),
        ('airtel_send_money', 'Airtel Send Money'),
        ('bank_transfer', 'Bank Transfer'),
        ('card', 'Credit/Debit Card')
    ]
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payment_methods')
    type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    till_number = models.CharField(max_length=20, blank=True, null=True)
    business_number = models.CharField(max_length=25, blank=True, null=True)
    paybill_account_number = models.CharField(max_length=25, blank=True, null=True)
    bank_account_number = models.CharField(max_length=25, blank=True, null=True)
    bank_name = models.CharField(max_length=70, blank=True, null=True)
    card_number = models.CharField(max_length=30, blank=True, null=True)

    def clean(self):
        if self.type == 'mpesa_till' and not self.till_number:
            raise ValidationError("Till number is required for M-Pesa Till.")
        elif self.type == 'mpesa_paybill':
            if not self.business_number or not self.paybill_account_number:
                raise ValidationError("Paybill and account number are required for mpesa Paybill.")
        elif self.type == 'bank_transfer':
            if not self.bank_name or not self.bank_account_number:
                raise ValidationError('Bank name and account number are required for bank transfers.')
        elif self.type == 'card' and not self.card_number:
            raise ValidationError("Card number is required for card payment.")
        
    def __str__(self):
        return f"{self.business.name}: {self.type} - {self.till_number}"


class BusinessReview(models.Model):
    product = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='business_reviews')
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    orders_complete = models.IntegerField(default=0)
    orders_pending = models.IntegerField(default=0)
    canceled_orders = models.IntegerField(default=0)
    comment = models.TextField(blank=True)
    mpesa_code = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta():
        unique_together = ['user']

    def clean(self):
        if self.product.owner == self.user:
            raise ValidationError("You cannot review your own business.")

    def __str__(self):
        return f"{self.user.username}"