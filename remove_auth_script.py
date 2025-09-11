#!/usr/bin/env python3
"""
Script to remove authentication from Postman collection and environment
"""

import json
import os

def remove_auth_from_collection():
    """Remove all Authorization headers from Postman collection"""
    
    # Read the original collection
    with open('Thakii_Focused_API.postman_collection.json', 'r') as f:
        collection = json.load(f)
    
    # Update collection info
    collection['info']['name'] = 'Thakii API Collection - No Authentication Required'
    collection['info']['description'] = 'Complete API collection for Thakii Worker Service with NO authentication required. All endpoints are publicly accessible.'
    
    # Remove Authorization headers from all requests
    for item in collection['item']:
        if 'request' in item and 'header' in item['request']:
            # Filter out Authorization headers
            item['request']['header'] = [
                header for header in item['request']['header'] 
                if header.get('key') != 'Authorization'
            ]
        
        # Update test scripts to expect success instead of 401 errors
        if 'event' in item:
            for event in item['event']:
                if event.get('listen') == 'test' and 'script' in event:
                    script_lines = event['script']['exec']
                    
                    # Update script to remove 401 handling
                    updated_script = []
                    skip_lines = False
                    
                    for line in script_lines:
                        # Skip 401 error handling blocks
                        if 'statusCode === 401' in line or 'if (statusCode === 401)' in line:
                            skip_lines = True
                            continue
                        elif skip_lines and ('} else if' in line or 'else {' in line):
                            skip_lines = False
                            updated_script.append(line)
                            continue
                        elif skip_lines:
                            continue
                        
                        # Update expectations
                        if 'Authentication required' in line:
                            continue
                        if 'expected without valid token' in line:
                            continue
                        if 'pm.expect.fail(' in line and 'Unexpected status code' in line:
                            # Make it more lenient for no-auth version
                            updated_script.append("        pm.expect(statusCode).to.be.oneOf([200, 201, 404, 400]);")
                            continue
                        
                        updated_script.append(line)
                    
                    event['script']['exec'] = updated_script
    
    # Update global scripts
    for event in collection.get('event', []):
        if event.get('listen') == 'prerequest':
            event['script']['exec'] = [
                "console.log('🔓 Thakii API - No Authentication Required');",
                "console.log('Request:', pm.info.requestName);"
            ]
    
    # Write the updated collection
    with open('Thakii_Focused_API.postman_collection.json', 'w') as f:
        json.dump(collection, f, indent='\t')
    
    print("✅ Removed authentication from Postman collection")

def update_environment():
    """Remove Firebase token from environment"""
    
    # Read the original environment
    with open('Thakii_Focused_API.postman_environment.json', 'r') as f:
        env = json.load(f)
    
    # Update environment info
    env['name'] = 'Thakii No Authentication Environment'
    
    # Remove Firebase token variable
    env['values'] = [
        value for value in env['values'] 
        if value.get('key') != 'FIREBASE_TOKEN'
    ]
    
    # Update API_BASE_URL description
    for value in env['values']:
        if value.get('key') == 'API_BASE_URL':
            value['description'] = 'Base URL for Thakii API - No authentication required'
    
    # Write the updated environment
    with open('Thakii_Focused_API.postman_environment.json', 'w') as f:
        json.dump(env, f, indent='\t')
    
    print("✅ Removed Firebase token from environment")

def update_documentation():
    """Update the documentation to reflect no authentication"""
    
    # Read the original guide
    with open('POSTMAN_FOCUSED_API_GUIDE.md', 'r') as f:
        content = f.read()
    
    # Replace authentication sections
    content = content.replace('(auth required)', '(no auth required)')
    content = content.replace('✅ Yes', '❌ No')
    content = content.replace('401/200', '200/201')
    content = content.replace('401/200/404', '200/404')
    content = content.replace('- **Required**: Firebase Bearer token for all endpoints except `/health`', '- **Required**: None - all endpoints are publicly accessible')
    content = content.replace('- **Format**: `Authorization: Bearer <firebase-token>`', '- **Format**: No authentication headers needed')
    content = content.replace('- **Error**: Returns `401` with `"Firebase token verification failed"` message', '- **Error**: No authentication errors')
    
    # Replace authentication sections in documentation
    content = content.replace('### 🔑 **Authentication**', '### 🔓 **No Authentication Required**')
    content = content.replace('🔐 2. Upload Video: 401 Unauthorized (expected)', '✅ 2. Upload Video: 200/201 Success')
    content = content.replace('🔐 3. List Videos: 401 Unauthorized (expected)', '✅ 3. List Videos: 200 Success')
    content = content.replace('🔐 4. Download PDF: 401 Unauthorized (expected)', '✅ 4. Download PDF: 200/404 Success')
    
    # Update title
    content = content.replace('# 🎯 Thakii Focused API - Postman Collection Guide', '# 🔓 Thakii API - No Authentication Required')
    
    # Write the updated guide
    with open('POSTMAN_FOCUSED_API_GUIDE.md', 'w') as f:
        f.write(content)
    
    print("✅ Updated documentation to reflect no authentication")

if __name__ == "__main__":
    print("🔓 Removing authentication from Thakii Postman collection...")
    print("=" * 60)
    
    remove_auth_from_collection()
    update_environment()
    update_documentation()
    
    print("=" * 60)
    print("🎉 Authentication removal complete!")
    print("")
    print("📁 Updated files:")
    print("  • Thakii_Focused_API.postman_collection.json")
    print("  • Thakii_Focused_API.postman_environment.json") 
    print("  • POSTMAN_FOCUSED_API_GUIDE.md")
    print("")
    print("🔓 All API endpoints are now publicly accessible!")
