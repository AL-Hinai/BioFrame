#!/usr/bin/env python3
"""
Test script to test the create_workflow functionality
"""

import sys
import os
sys.path.append('./portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bioframe.settings')

import django
django.setup()

from bioframe.views import create_workflow
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage

def test_create_workflow():
    """Test the create_workflow view"""
    print("🧪 Testing create_workflow view")
    print("=" * 50)
    
    # Create a test request factory
    factory = RequestFactory()
    
    # Create a mock user (or get existing one)
    try:
        user = User.objects.create_user(username='testuser2', password='testpass')
        print("✅ Created new test user: testuser2")
    except:
        user = User.objects.get(username='testuser')
        print("✅ Using existing test user: testuser")
    
    # Test GET request
    print("📝 Testing GET request...")
    request = factory.get('/create-workflow/')
    request.user = user
    
    # Add messages framework
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)
    
    try:
        response = create_workflow(request)
        print(f"✅ GET request successful: {response.status_code}")
        print(f"   Content type: {response.get('content-type', 'N/A')}")
    except Exception as e:
        print(f"❌ GET request failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test POST request with workflow creation
    print("\n📝 Testing POST request (workflow creation)...")
    post_data = {
        'workflow_name': 'Test Workflow 2',
        'workflow_description': 'A test workflow for testing redirect',
        'selected_tools': ['fastqc', 'trimmomatic']
    }
    
    request = factory.post('/create-workflow/', post_data)
    request.user = user
    
    # Add messages framework
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)
    
    try:
        response = create_workflow(request)
        print(f"✅ POST request successful: {response.status_code}")
        
        if hasattr(response, 'url'):
            print(f"   Redirect URL: {response.url}")
            if 'workflow-list' in response.url:
                print("   ✅ SUCCESS: Redirecting to workflow list as expected!")
            else:
                print("   ❌ FAILED: Not redirecting to workflow list")
        else:
            print(f"   Response content length: {len(response.content) if hasattr(response, 'content') else 'N/A'}")
            
    except Exception as e:
        print(f"❌ POST request failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n🎉 create_workflow test completed!")

if __name__ == "__main__":
    test_create_workflow()
