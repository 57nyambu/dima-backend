from django.conf import settings
from datetime import datetime
import base64
import requests
import logging

logger = logging.getLogger(__name__)


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
        try:
            url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
            
            logger.info(f"Authenticating with M-Pesa...")
            logger.info(f"Consumer Key: {self.consumer_key[:10]}..." if self.consumer_key else "Consumer Key: NOT SET")
            
            response = requests.get(
                url,
                auth=(self.consumer_key, self.consumer_secret),
                timeout=30
            )
            
            logger.info(f"M-Pesa Auth Response Status: {response.status_code}")
            logger.info(f"M-Pesa Auth Response Body: {response.text}")
            
            if response.status_code != 200:
                logger.error(f"M-Pesa Auth Failed with status {response.status_code}: {response.text}")
                return None
            
            try:
                data = response.json()
                logger.info(f"M-Pesa Auth JSON Response: {data}")
            except ValueError as e:
                logger.error(f"Failed to parse auth response as JSON: {response.text}")
                return None
            
            self.auth_token = data.get('access_token')
            
            if not self.auth_token:
                logger.error(f"No access token in response. Keys in response: {list(data.keys())}")
                return None
            
            logger.info(f"Authentication successful! Token: {self.auth_token[:20]}...")
            return self.auth_token
        except requests.exceptions.RequestException as e:
            logger.error(f"M-Pesa authentication network error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"M-Pesa authentication unexpected error: {str(e)}", exc_info=True)
            return None

    def stk_push(self, phone, amount, order_id, description):
        """Initiate STK push to customer"""
        try:
            auth_token = self.authenticate()
            
            if not auth_token:
                return {
                    'ResponseCode': '1',
                    'errorCode': 'AUTH_FAILED',
                    'errorMessage': 'Failed to authenticate with M-Pesa'
                }
            
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
                "Amount": int(amount),
                "PartyA": phone,
                "PartyB": self.business_shortcode,
                "PhoneNumber": phone,
                "CallBackURL": self.callback_url,
                "AccountReference": f"ORDER{order_id}",
                "TransactionDesc": description[:20]  # Limit to 20 characters
            }

            headers = {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json"
            }

            logger.info(f"M-Pesa STK Push Request: Phone={phone}, Amount={amount}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            logger.info(f"M-Pesa STK Response Status: {response.status_code}")
            logger.info(f"M-Pesa STK Response Text: {response.text}")
            
            # Handle empty or invalid response
            if not response.text or response.text.strip() == '':
                logger.error("M-Pesa returned empty response")
                return {
                    'ResponseCode': '1',
                    'errorCode': 'EMPTY_RESPONSE',
                    'errorMessage': 'M-Pesa returned empty response'
                }
            
            try:
                return response.json()
            except ValueError as e:
                logger.error(f"Failed to parse M-Pesa response: {response.text}")
                return {
                    'ResponseCode': '1',
                    'errorCode': 'INVALID_JSON',
                    'errorMessage': f'Invalid response from M-Pesa: {response.text[:100]}'
                }
                
        except requests.exceptions.Timeout:
            logger.error("M-Pesa request timeout")
            return {
                'ResponseCode': '1',
                'errorCode': 'TIMEOUT',
                'errorMessage': 'Request to M-Pesa timed out'
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"M-Pesa request error: {str(e)}")
            return {
                'ResponseCode': '1',
                'errorCode': 'REQUEST_ERROR',
                'errorMessage': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected M-Pesa error: {str(e)}")
            return {
                'ResponseCode': '1',
                'errorCode': 'UNKNOWN_ERROR',
                'errorMessage': str(e)
            }


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
        dict: M-Pesa API response with success flag
    """
    try:
        # Validate inputs
        if not phone_number:
            return {
                'success': False,
                'errorCode': 'INVALID_PHONE',
                'errorMessage': 'Phone number is required'
            }
        
        if not amount or float(amount) <= 0:
            return {
                'success': False,
                'errorCode': 'INVALID_AMOUNT',
                'errorMessage': 'Valid amount is required'
            }
        
        # Ensure phone number is in correct format (254XXXXXXXXX)
        phone = str(phone_number).strip()
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+254'):
            phone = phone[1:]
        
        if not phone.startswith('254') or len(phone) != 12:
            return {
                'success': False,
                'errorCode': 'INVALID_PHONE_FORMAT',
                'errorMessage': f'Invalid phone format. Expected 254XXXXXXXXX, got {phone}'
            }
        
        logger.info(f"Initiating STK Push: Phone={phone}, Amount={amount}, Ref={account_reference}")
        
        gateway = MpesaGateway()
        
        # Extract order ID from account reference if possible
        order_id = account_reference.replace('ORDER-', '').replace('ORDER', '').strip()
        if not order_id:
            order_id = '1'
        
        response = gateway.stk_push(
            phone=phone,
            amount=int(float(amount)),
            order_id=order_id,
            description=transaction_desc[:20] if transaction_desc else 'Payment'
        )
        
        logger.info(f"M-Pesa Response: {response}")
        
        # Check if request was successful
        if response.get('ResponseCode') == '0':
            return {
                'success': True,
                'CheckoutRequestID': response.get('CheckoutRequestID'),
                'MerchantRequestID': response.get('MerchantRequestID'),
                'ResponseDescription': response.get('ResponseDescription', 'STK Push initiated'),
                'CustomerMessage': response.get('CustomerMessage', 'Please check your phone')
            }
        else:
            error_message = response.get('errorMessage') or response.get('ResponseDescription') or 'Failed to initiate payment'
            return {
                'success': False,
                'errorCode': response.get('errorCode', response.get('ResponseCode')),
                'errorMessage': error_message
            }
    
    except Exception as e:
        logger.error(f"STK Push Exception: {str(e)}")
        return {
            'success': False,
            'errorCode': 'EXCEPTION',
            'errorMessage': str(e)
        }
