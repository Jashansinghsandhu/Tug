#!/usr/bin/env python3
"""
Instagram Collaboration Checker - Terminal Version
Simple command line tool to check Instagram collaborations
"""

import requests
import sys

def get_instagram_data(username):
    """Get Instagram collaboration data"""
    print(f"Checking @{username}...")
    
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    headers = {
        "X-IG-App-ID": "936619743392459",
        "Referer": f"https://www.instagram.com/{username}/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 404:
            print("❌ User not found")
            return
        elif response.status_code != 200:
            print(f"❌ Error {response.status_code}")
            return
        
        data = response.json()
        user = data["data"]["user"]
        
        username = user.get("username", "Unknown")
        is_private = user.get("is_private", False)
        profile_type = "🔒 Private" if is_private else "🔓 Public"
        
        posts = user.get("edge_owner_to_timeline_media", {}).get("edges", [])
        
        print(f"\n📊 Results for @{username}")
        print(f"{profile_type} profile")
        print(f"📈 {len(posts)} posts found")
        print("-" * 40)
        
        if not posts:
            print("No posts found")
            return
        
        for i, post in enumerate(posts[:5], 1):  # Show 5 posts
            post_data = post["node"]
            shortcode = post_data["shortcode"]
            owner = post_data["owner"]["username"]
            
            print(f"\n📌 Post {i}:")
            print(f"🔗 https://instagram.com/p/{shortcode}")
            print(f"👤 Owner: @{owner}")
            
            # Check collaborators
            collabs = post_data.get("edge_media_to_tagged_user", {}).get("edges", [])
            if collabs:
                collab_names = []
                for collab in collabs:
                    collab_names.append(f"@{collab['node']['user']['username']}")
                print(f"🤝 With: {', '.join(collab_names)}")
            else:
                print("🤝 No collaborators")
        
        if len(posts) > 5:
            print(f"\n📊 Showing 5 of {len(posts)} posts")
        
        print("-" * 40)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def main():
    """Main function"""
    print("📸 Instagram Collaboration Checker")
    print("=" * 40)
    
    if len(sys.argv) > 1:
        # Command line argument
        username = sys.argv[1].replace("@", "")
        get_instagram_data(username)
    else:
        # Interactive mode
        print("Enter Instagram username (or 'quit' to exit)")
        
        while True:
            try:
                username = input("\n👤 Username: ").strip()
                
                if username.lower() in ['quit', 'exit', 'q']:
                    print("Goodbye!")
                    break
                
                if not username:
                    print("Please enter a username")
                    continue
                
                # Clean username
                username = username.replace("@", "")
                
                # Validate username
                if not username.replace('_', '').replace('.', '').isalnum():
                    print("Invalid username format")
                    continue
                
                get_instagram_data(username)
                
            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")

if __name__ == "__main__":
    main()