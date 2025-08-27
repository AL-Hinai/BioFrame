#!/usr/bin/env python3
"""
Script to create a test user for BioFrame testing
"""

import os
import sys
import django

# Add the portal directory to the Python path
sys.path.append('./portal')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bioframe.settings')
django.setup()

from django.contrib.auth.models import User

def create_test_user():
    """Create a test user for BioFrame testing"""
    username = 'testuser'
    email = 'test@bioframe.com'
    password = 'testpass123'
    
    try:
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            print(f"✅ User '{username}' already exists")
        else:
            # Create new user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            print(f"✅ Created user '{username}' with email '{email}'")
        
        print(f"📋 User details:")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Password: {password}")
        print(f"   Is active: {user.is_active}")
        print(f"   Is staff: {user.is_staff}")
        print(f"   Date joined: {user.date_joined}")
        
        return user
        
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None

if __name__ == "__main__":
    print("🧪 Creating test user for BioFrame...")
    user = create_test_user()
    
    if user:
        print("\n🎉 Test user created successfully!")
        print(f"🔑 You can now login with:")
        print(f"   Username: {user.username}")
        print(f"   Password: {user.password if hasattr(user, 'password') else 'testpass123'}")
    else:
        print("\n❌ Failed to create test user")
