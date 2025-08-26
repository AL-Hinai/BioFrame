#!/usr/bin/env python3
"""
Test script for workflow_list view
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bioframe.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from bioframe.views import workflow_list

def test_workflow_list():
    """Test the workflow_list view"""
    print("🧪 Testing workflow_list view")
    print("=" * 50)
    
    # Create a test request factory
    factory = RequestFactory()
    
    # Get or create a test user
    try:
        user = User.objects.first()
        if user:
            print(f"✅ Using existing user: {user.username}")
        else:
            user = User.objects.create_user(username='testuser3', password='testpass')
            print(f"✅ Created new test user: {user.username}")
    except Exception as e:
        print(f"❌ Error with user: {e}")
        return
    
    # Test GET request to workflow_list
    print("📝 Testing workflow_list view...")
    request = factory.get('/workflow-list/')
    request.user = user
    
    try:
        response = workflow_list(request)
        print(f"✅ Response status: {response.status_code}")
        print(f"   Response type: {type(response)}")
        print(f"   Response content type: {response.get('content-type', 'N/A')}")
        
        # Check if it's a render response
        if hasattr(response, 'context_data'):
            context = response.context_data
            print(f"   Context keys: {list(context.keys())}")
            print(f"   Templates count: {len(context.get('templates', []))}")
            print(f"   User workflows count: {len(context.get('user_workflows', []))}")
            print(f"   All workflows count: {len(context.get('workflows', []))}")
        elif hasattr(response, 'context'):
            context = response.context
            print(f"   Context keys: {list(context.keys())}")
            print(f"   Templates count: {len(context.get('templates', []))}")
            print(f"   User workflows count: {len(context.get('user_workflows', []))}")
            print(f"   All workflows count: {len(context.get('workflows', []))}")
        else:
            print("   No context data available")
            print(f"   Response attributes: {dir(response)}")
            
            # Try to access content
            if hasattr(response, 'content'):
                print(f"   Content length: {len(response.content)}")
                print(f"   Content preview: {str(response.content)[:200]}...")
            
    except Exception as e:
        print(f"❌ Error in workflow_list view: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n🎉 workflow_list test completed!")

if __name__ == "__main__":
    test_workflow_list()

