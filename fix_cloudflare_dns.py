#!/usr/bin/env python3
"""
Cloudflare DNS Fix Script
Automatically configures thakii-02.fanusdigital.site to point to the server IP
"""

import requests
import json
import sys
import os

def fix_cloudflare_dns():
    # Configuration
    domain = "fanusdigital.site"
    subdomain = "thakii-02"
    server_ip = "81.204.248.240"
    full_domain = f"{subdomain}.{domain}"
    
    # Get API token from environment or GitHub secret
    api_token = os.getenv('CLOUDFLARE_SERVICE_TOKEN')
    if not api_token:
        print("❌ Error: CLOUDFLARE_SERVICE_TOKEN environment variable not set")
        print("🔧 Run: export CLOUDFLARE_SERVICE_TOKEN='your_token_here'")
        return False
    
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    
    print(f"🚀 === CLOUDFLARE DNS FIX FOR {full_domain} ===")
    print()
    
    # Step 1: Get Zone ID
    print("1️⃣ Getting Zone ID for fanusdigital.site...")
    zones_url = f"https://api.cloudflare.com/client/v4/zones?name={domain}"
    
    try:
        response = requests.get(zones_url, headers=headers)
        zones_data = response.json()
        
        if not zones_data['success']:
            print(f"❌ Error getting zones: {zones_data['errors']}")
            return False
            
        if not zones_data['result']:
            print(f"❌ Domain {domain} not found in Cloudflare")
            return False
            
        zone_id = zones_data['result'][0]['id']
        print(f"✅ Zone ID: {zone_id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Step 2: Check existing DNS records
    print(f"2️⃣ Checking existing DNS records for {subdomain}...")
    dns_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={full_domain}"
    
    try:
        response = requests.get(dns_url, headers=headers)
        dns_data = response.json()
        
        if not dns_data['success']:
            print(f"❌ Error getting DNS records: {dns_data['errors']}")
            return False
            
        existing_records = dns_data['result']
        print(f"📋 Found {len(existing_records)} existing records")
        
        # Find A record
        a_record = None
        for record in existing_records:
            if record['type'] == 'A':
                a_record = record
                break
                
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Step 3: Update or create A record
    if a_record:
        print(f"3️⃣ Updating existing A record...")
        print(f"   Current: {a_record['content']} (Proxied: {a_record['proxied']})")
        print(f"   New: {server_ip} (Proxied: True)")
        
        # Update existing record
        record_id = a_record['id']
        update_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
        
        data = {
            "type": "A",
            "name": subdomain,
            "content": server_ip,
            "proxied": True,
            "comment": f"Updated by API - Thakii Worker Service - {full_domain}"
        }
        
        try:
            response = requests.put(update_url, headers=headers, json=data)
            result = response.json()
            
            if result['success']:
                print("✅ DNS record updated successfully!")
                print(f"   {full_domain} → {server_ip} (Proxied)")
            else:
                print(f"❌ Update failed: {result['errors']}")
                return False
                
        except Exception as e:
            print(f"❌ Error updating record: {e}")
            return False
            
    else:
        print(f"3️⃣ Creating new A record...")
        
        # Create new record
        create_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
        
        data = {
            "type": "A",
            "name": subdomain,
            "content": server_ip,
            "proxied": True,
            "comment": f"Created by API - Thakii Worker Service - {full_domain}"
        }
        
        try:
            response = requests.post(create_url, headers=headers, json=data)
            result = response.json()
            
            if result['success']:
                print("✅ DNS record created successfully!")
                print(f"   {full_domain} → {server_ip} (Proxied)")
            else:
                print(f"❌ Creation failed: {result['errors']}")
                return False
                
        except Exception as e:
            print(f"❌ Error creating record: {e}")
            return False
    
    # Step 4: Verify the change
    print("4️⃣ Verifying DNS change...")
    try:
        verify_response = requests.get(dns_url, headers=headers)
        verify_data = verify_response.json()
        
        if verify_data['success'] and verify_data['result']:
            record = verify_data['result'][0]
            print(f"✅ Verification successful:")
            print(f"   Name: {record['name']}")
            print(f"   Content: {record['content']}")
            print(f"   Proxied: {record['proxied']}")
            print(f"   Type: {record['type']}")
            
        print()
        print("🎉 === DNS CONFIGURATION COMPLETE ===")
        print(f"🌐 Your API should now be accessible at:")
        print(f"   https://{full_domain}/worker/health")
        print(f"   https://{full_domain}/worker/list")
        print()
        print("⏳ DNS propagation may take 1-5 minutes...")
        
        return True
        
    except Exception as e:
        print(f"⚠️  Verification error: {e}")
        return True  # Still consider success if update worked
        
if __name__ == "__main__":
    success = fix_cloudflare_dns()
    sys.exit(0 if success else 1)
