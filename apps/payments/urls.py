# payments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# DefaultRouter automatically generates URL patterns for ViewSets
router = DefaultRouter()

# Register PaymentViewSet - generates standard CRUD endpoints
# This creates:
# GET    /payments/                     - List all payments
# POST   /payments/                     - Create payment (initiate)
# GET    /payments/{id}/                - Get payment details
# PUT    /payments/{id}/                - Update payment (full)
# PATCH  /payments/{id}/                - Update payment (partial)
# DELETE /payments/{id}/                - Delete payment
router.register(r'payments', views.PaymentViewSet, basename='payment')

app_name = 'apps.payments'

urlpatterns = [
    # Router URLs - includes all ViewSet endpoints and custom actions
    # Custom actions from PaymentViewSet:
    # POST   /payments/{id}/verify/          - Verify payment status
    # POST   /payments/{id}/confirm/         - Manually confirm payment (admin)
    # POST   /payments/{id}/refund/          - Request refund
    # POST   /payments/mpesa-stk-push/       - Direct MPesa STK push
    # GET    /payments/by-order/{order_id}/  - Get payment by order
    path('', include(router.urls)),
    
    # Legacy endpoints (kept for backward compatibility)
    path('initiate/', views.InitiatePaymentView.as_view(), name='initiate_payment'),
    
    # Webhook endpoints (public, no auth required)
    path('mpesa-callback/', views.MPesaCallbackView.as_view(), name='mpesa_callback'),
    path('webhooks/mpesa/', views.MPesaCallbackView.as_view(), name='mpesa_webhook'),
]

"""
Payment API Endpoints Documentation
====================================

## Core Payment Endpoints (RESTful via ViewSet)

### 1. List All Payments
GET /api/payments/
- Returns list of payments for authenticated user
- Staff users see all payments
- Response: Paginated list of payments

Example Response:
{
    "count": 10,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "order": {...},
            "amount": "1000.00",
            "method": "mpesa",
            "mpesa_phone": "254722123456",
            "mpesa_code": "NLJ7RT56",
            "is_confirmed": true,
            "is_settled": false,
            "created_at": "2026-02-01T10:30:00Z"
        }
    ]
}

### 2. Create Payment (Initiate)
POST /api/payments/
- Initiates a new payment for an order
- For MPesa: triggers STK push to customer's phone
- For COD: auto-confirms payment
- For other methods: creates pending payment

Request Body:
{
    "order": 123,
    "method": "mpesa",  # mpesa|airtel|paypal|cod|card
    "mpesa_phone": "254722123456",  # Required for MPesa
    "amount": 1000.00  # Optional, auto-calculated from order
}

Success Response (MPesa):
{
    "success": true,
    "message": "MPesa payment request sent to your phone",
    "payment_id": 1,
    "checkout_request_id": "ws_CO_01022026103045678901234567890",
    "merchant_request_id": "12345-67890-1",
    "customer_message": "Please check your phone and enter PIN"
}

Error Response:
{
    "success": false,
    "error": "Failed to initiate MPesa payment",
    "error_code": "INVALID_PHONE"
}

### 3. Get Payment Details
GET /api/payments/{id}/
- Returns detailed information about a specific payment
- Only accessible by payment owner or staff

Response:
{
    "id": 1,
    "order": {
        "id": 123,
        "status": "confirmed",
        "business": {
            "id": 1,
            "name": "Shop Name"
        }
    },
    "amount": "1000.00",
    "method": "mpesa",
    "mpesa_phone": "254722123456",
    "mpesa_code": "NLJ7RT56",
    "is_confirmed": true,
    "is_settled": false,
    "created_at": "2026-02-01T10:30:00Z"
}

### 4. Verify Payment Status
POST /api/payments/{id}/verify/
- Check if payment has been confirmed
- Useful for polling payment status after STK push

Response:
{
    "verified": true,
    "message": "Payment already confirmed",
    "payment": {...}
}

### 5. Confirm Payment (Admin Only)
POST /api/payments/{id}/confirm/
- Manually confirm a payment
- Restricted to staff users
- Updates order status to 'confirmed'

Request Body:
{
    "mpesa_code": "NLJ7RT56"  # Optional
}

Response:
{
    "success": true,
    "message": "Payment confirmed successfully",
    "payment": {...}
}

### 6. Request Refund
POST /api/payments/{id}/refund/
- Submit a refund request for confirmed payment
- Changes order status to 'refund_requested'

Request Body:
{
    "reason": "Product not received"
}

Response:
{
    "success": true,
    "message": "Refund request submitted",
    "note": "Your refund will be processed within 5-7 business days"
}

### 7. Direct MPesa STK Push
POST /api/payments/mpesa-stk-push/
- Directly initiate MPesa STK push without creating payment record
- Useful for testing or alternative flows

Request Body:
{
    "phone_number": "254722123456",
    "amount": 1000,
    "order_id": 123,
    "description": "Payment for Order 123"
}

Response:
{
    "success": true,
    "message": "Request accepted for processing",
    "checkout_request_id": "ws_CO_01022026103045678901234567890",
    "customer_message": "Please check your phone"
}

### 8. Get Payment by Order
GET /api/payments/by-order/{order_id}/
- Retrieve payment information using order ID
- Convenient when you only have order ID

Response: Same as payment details endpoint

## Legacy Endpoints

### Initiate Payment (Legacy)
POST /api/payments/initiate/
- Old endpoint, kept for backward compatibility
- Use POST /api/payments/ instead

## Webhook Endpoints (Public, No Auth)

### MPesa Callback
POST /api/payments/mpesa-callback/
POST /api/payments/webhooks/mpesa/
- Receives payment confirmation from Safaricom
- Updates payment and order status automatically
- Should be configured in Safaricom developer portal

Request Body (from Safaricom):
{
    "Body": {
        "stkCallback": {
            "ResultCode": 0,
            "ResultDesc": "Success",
            "CheckoutRequestID": "ws_CO_01022026103045678901234567890",
            "CallbackMetadata": {
                "Item": [
                    {"Name": "Amount", "Value": 1000},
                    {"Name": "MpesaReceiptNumber", "Value": "NLJ7RT56"},
                    {"Name": "PhoneNumber", "Value": "254722123456"}
                ]
            }
        }
    }
}

Response:
{
    "ResultCode": 0,
    "ResultDesc": "Success"
}

## Payment Methods Supported

1. **MPesa (mpesa)**
   - Requires: mpesa_phone
   - Uses: STK Push API
   - Auto-confirmation via callback

2. **Airtel Money (airtel)**
   - Requires: airtel_phone
   - Status: Pending integration

3. **Cash on Delivery (cod)**
   - Auto-confirmed
   - Business must allow COD

4. **PayPal (paypal)**
   - Status: Pending integration

5. **Credit/Debit Card (card)**
   - Status: Pending integration

## Error Codes

- `AUTH_FAILED` - MPesa authentication failed
- `INVALID_PHONE` - Invalid phone number format
- `INVALID_AMOUNT` - Amount must be greater than 0
- `TIMEOUT` - Request to MPesa timed out
- `REQUEST_ERROR` - Network error
- `UNKNOWN_ERROR` - Unexpected error occurred

## Testing

### Test MPesa Payment Flow

1. Create payment:
```bash
curl -X POST http://localhost:8000/api/payments/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "order": 123,
    "method": "mpesa",
    "mpesa_phone": "254722123456"
  }'
```

2. Check phone for STK push prompt

3. Verify payment:
```bash
curl -X POST http://localhost:8000/api/payments/1/verify/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Test COD Payment

```bash
curl -X POST http://localhost:8000/api/payments/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "order": 123,
    "method": "cod"
  }'
```

## Integration Notes

1. **For Frontend Developers:**
   - Use POST /api/payments/ to initiate payments
   - Poll GET /api/payments/{id}/verify/ for MPesa status
   - Show user-friendly messages from response
   - Handle error_code for specific error handling

2. **For Safaricom Integration:**
   - Set callback URL to: https://yourdomain.com/api/payments/mpesa-callback/
   - Use sandbox credentials for testing
   - Switch to production credentials when live

3. **For Admin Panel:**
   - Use POST /api/payments/{id}/confirm/ for manual confirmations
   - Monitor payments via GET /api/payments/
   - Filter by is_confirmed, is_settled status

4. **Security:**
   - All endpoints except webhooks require authentication
   - Users can only access their own payments
   - Staff can access all payments
   - Webhook endpoint validates Safaricom IP (TODO)
"""
