# E-Commerce Ecosystem Platform API Documentation

## Overview
This documentation describes the API endpoints for managing businesses, payment methods, and reviews in our e-commerce ecosystem platform.

## Authentication
- All endpoints require authentication
- Users must be logged in to access any functionality
- Authentication is handled via JWT (JSON Web Tokens) or session-based authentication
- Unauthenticated requests will receive a 401 Unauthorized response

## Security Considerations
- Users can only access and modify their own resources
- Business creation and management is tied to the authenticated user
- Payment methods are scoped to the user's businesses
- Review creation is restricted to prevent duplicate reviews

## Endpoint: Business Management

### 1. Create a Business
**Endpoint:** `POST /api/businesses/`

**Request Payload:**
```json
{
    "name": "Tech Haven",
    "business_type": "electronics",
    "description": "Premium electronics store",
    "kra_pin": "A123456789",
    "business_reg_no": "REG-2024-001",
    "payment_methods": [
        {
            "type": "mpesa_till",
            "till_number": "987654"
        },
        {
            "type": "bank_transfer",
            "bank_name": "Kenya Commercial Bank",
            "bank_account_number": "1234567890"
        }
    ]
}
```

**Successful Response:**
```json
{
    "id": 1,
    "name": "Tech Haven",
    "slug": "tech-haven",
    "business_type": "electronics",
    "description": "Premium electronics store",
    "kra_pin": "A123456789",
    "business_reg_no": "REG-2024-001",
    "is_verified": false,
    "created_at": "2024-05-12T10:30:45.123Z",
    "updated_at": "2024-05-12T10:30:45.123Z",
    "payment_methods": [
        {
            "type": "mpesa_till",
            "till_number": "987654"
        },
        {
            "type": "bank_transfer",
            "bank_name": "Kenya Commercial Bank",
            "bank_account_number": "1234567890"
        }
    ]
}
```

### 2. List Businesses
**Endpoint:** `GET /api/businesses/`

**Response:**
```json
{
    "count": 2,
    "next": null,
    "previous": null,
    "results": [
        {
            "id": 1,
            "name": "Tech Haven",
            "slug": "tech-haven",
            "business_type": "electronics",
            "is_verified": false
        },
        {
            "id": 2,
            "name": "Fresh Produce",
            "slug": "fresh-produce",
            "business_type": "agriculture",
            "is_verified": true
        }
    ]
}
```

### 3. Retrieve Business Details
**Endpoint:** `GET /api/businesses/{slug}/`

**Response:**
```json
{
    "id": 1,
    "name": "Tech Haven",
    "slug": "tech-haven",
    "business_type": "electronics",
    "description": "Premium electronics store",
    "kra_pin": "A123456789",
    "business_reg_no": "REG-2024-001",
    "is_verified": false,
    "created_at": "2024-05-12T10:30:45.123Z",
    "updated_at": "2024-05-12T10:30:45.123Z"
}
```

### 4. Update Business
**Endpoint:** `PUT /api/businesses/{slug}/`

**Request Payload:**
```json
{
    "name": "Tech Haven Updated",
    "description": "Your one-stop shop for premium electronics",
    "payment_methods": [
        {
            "type": "bank_transfer",
            "bank_name": "Equity Bank",
            "bank_account_number": "0987654321"
        }
    ]
}
```

## Endpoint: Payment Methods

### 1. List Payment Methods
**Endpoint:** `GET /api/payment-methods/`

**Response:**
```json
{
    "count": 2,
    "results": [
        {
            "type": "mpesa_till",
            "till_number": "987654",
            "business_name": "Tech Haven"
        },
        {
            "type": "bank_transfer",
            "bank_name": "Equity Bank",
            "bank_account_number": "0987654321",
            "business_name": "Fresh Produce"
        }
    ]
}
```

## Endpoint: Reviews

### 1. Create a Review
**Endpoint:** `POST /api/reviews/`

**Request Payload:**
```json
{
    "product": 1,
    "rating": 4,
    "comment": "Great service and products!",
    "mpesa_code": "ABC123"
}
```

**Successful Response:**
```json
{
    "id": 1,
    "product": 1,
    "user": 5,
    "rating": 4,
    "comment": "Great service and products!",
    "mpesa_code": "ABC123",
    "created_at": "2024-05-12T11:45:30.456Z"
}
```

## Validation Rules

### Business Validation
- Name is required
- Business type must be one of the predefined categories
- KRA PIN and business registration number are optional
- Slug is auto-generated from the business name

### Payment Method Validation
- Payment type must be one of:
  - M-Pesa Till: Requires till number
  - M-Pesa Paybill: Requires business number and account number
  - Bank Transfer: Requires bank name and account number
  - Card Payment: Requires card number

### Review Validation
- Rating must be between 1 and 5
- Users can only review a business once
- Mpesa code is optional

## Error Handling

### Common Error Responses

1. Authentication Error
```json
{
    "detail": "Authentication credentials were not provided."
}
```

2. Permission Error
```json
{
    "detail": "You do not have permission to perform this action."
}
```

3. Validation Error
```json
{
    "name": ["This field is required."],
    "payment_methods": [
        {
            "type": ["Invalid payment method type."],
            "till_number": ["Till number is required for M-Pesa Till."]
        }
    ]
}
```

## Business Categories
- Fashion & Clothing
- Electronics
- Agriculture & Farm Produce
- Food & Groceries
- Health & Pharmacy
- Logistics & Transport Services
- Entertainment & Events
- Manufacture & Processing
- Small/Medium Enterprise
- Second-Hand Dealer
- Others

## Payment Method Types
- M-Pesa Till
- M-Pesa Paybill
- M-Pesa Send Money
- Airtel Send Money
- Bank Transfer
- Credit/Debit Card

## Best Practices
1. Always include authentication token in requests
2. Handle potential validation errors in your client
3. Use HTTPS for all API communications
4. Implement proper error handling
5. Validate input data before submission

## Potential Improvements
- Add more detailed business verification process
- Implement advanced search and filtering
- Add support for multiple languages
- Create more granular permission levels

## Notes
- Businesses are not automatically verified
- Users can only see their own unverified businesses and all verified businesses
- Payment methods are closely tied to business creation