"""
Check Resend domain DNS records
"""
import resend

resend.api_key = "re_Fwib8wtj_MW8Mpg8u2JkKJFryB5Jxdw8d"

print("=" * 60)
print("RESEND DOMAIN DNS RECORDS")
print("=" * 60)

try:
    domain_info = resend.Domains.get(domain_id="58ff541f-468e-4ae7-8997-bb3c497c4178")
    
    print(f"\nDomain: {domain_info.get('name')}")
    print(f"Status: {domain_info.get('status')}")
    print(f"Region: {domain_info.get('region')}")
    print(f"Created: {domain_info.get('created_at')}")
    
    print("\n📋 DNS Records Required:")
    print("-" * 60)
    
    records = domain_info.get('records', [])
    if records:
        for i, record in enumerate(records, 1):
            print(f"\n{i}. {record.get('record_type')} Record")
            print(f"   Name:     {record.get('name')}")
            print(f"   Value:    {record.get('value')}")
            print(f"   Status:   {record.get('status')}")
            if record.get('priority'):
                print(f"   Priority: {record.get('priority')}")
    else:
        print("   No DNS records found")
    
    print("\n" + "=" * 60)
    print("INSTRUCTIONS:")
    print("=" * 60)
    print("""
1. Go to your DNS provider (e.g., Cloudflare, GoDaddy, Namecheap)
2. Add the DNS records shown above
3. Wait 24-48 hours for DNS propagation
4. Run this script again to check verification status

OR

Use onboarding@resend.dev domain (works immediately):
- Update DEFAULT_FROM_EMAIL to 'Dima Marketplace <onboarding@resend.dev>'
- This domain is pre-verified by Resend for testing
""")
    
except Exception as e:
    print(f"✗ Failed to get domain info: {e}")
