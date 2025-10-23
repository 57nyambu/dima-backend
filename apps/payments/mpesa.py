from django.conf import settings
from datetime import datetime
import base64
import requests


class MpesaGateway:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.business_shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.callback_url = settings.MPESA_CALLBACK_URL
        self.auth_token = None

    def authenticate(self):
        """Get access token from Safaricom API"""
        url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
        response = requests.get(
            url,
            auth=(self.consumer_key, self.consumer_secret)
        )
        self.auth_token = response.json().get('access_token')
        return self.auth_token

    def stk_push(self, phone, amount, order_id, description):
        """Initiate STK push to customer"""
        auth_token = self.authenticate()
        url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password = base64.b64encode(
            f"{self.business_shortcode}{self.passkey}{timestamp}".encode()
        ).decode()

        payload = {
            "BusinessShortCode": self.business_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone,
            "PartyB": self.business_shortcode,
            "PhoneNumber": phone,
            "CallBackURL": self.callback_url,
            "AccountReference": f"ORDER{order_id}",
            "TransactionDesc": description
        }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }

        response = requests.post(url, json=payload, headers=headers)
        return response.json()


# Helper function for easy import
def initiate_stk_push(phone_number, amount, account_reference, transaction_desc):
    """
    Convenience function to initiate M-Pesa STK Push
    
    Args:
        phone_number: Customer phone number (254XXXXXXXXX)
        amount: Amount to charge
        account_reference: Order reference
        transaction_desc: Transaction description
    
    Returns:
        dict: M-Pesa API response
    """
    gateway = MpesaGateway()
    
    try:
        # Extract order ID from account reference if possible
        order_id = account_reference.replace('ORDER-', '').replace('ORDER', '')
        
        response = gateway.stk_push(
            phone=phone_number,
            amount=int(amount),
            order_id=order_id,
            description=transaction_desc
        )
        
        # Check if request was successful
        if response.get('ResponseCode') == '0':
            return {
                'success': True,
                'CheckoutRequestID': response.get('CheckoutRequestID'),
                'MerchantRequestID': response.get('MerchantRequestID'),
                'ResponseDescription': response.get('ResponseDescription'),
                'CustomerMessage': response.get('CustomerMessage')
            }
        else:
            return {
                'success': False,
                'errorCode': response.get('errorCode'),
                'errorMessage': response.get('errorMessage', 'Failed to initiate payment')
            }
    
    except Exception as e:
        return {
            'success': False,
            'errorMessage': str(e)
        }
