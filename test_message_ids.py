#!/usr/bin/env python3
"""
Test the improved message ID generation without time drift issues
"""

import sys
sys.path.append('.')
from scraper import RSDNScraper

def test_time_drift_resistance():
    """Test that message IDs are stable despite time drift"""
    print("🔍 Testing time drift resistance:")
    print("=" * 80)
    
    scraper = RSDNScraper()
    
    # Simulate the same thread state with different relative times (time drift)
    thread_url = '/forum/flame.politics.unfiltered/8998183'
    thread_title = 'Important Discussion'
    original_author = 'ThreadStarter'
    forum = 'flame.politics.unfiltered'
    last_reply_user = 'SomeUser'
    
    print("Scenario: Same thread state, but time drifts")
    print("-" * 50)
    
    # Same thread state at different times (time drift simulation)
    times = ['5 мин', '6 мин', '7 мин', '8 мин', '9 мин']
    ids = []
    
    for i, time_str in enumerate(times, 1):
        message_id = scraper._generate_message_id(
            title=thread_title,
            author=original_author,
            forum=forum,
            time_posted=time_str,
            url=thread_url,
            last_reply_author=last_reply_user  # Same last reply author = no new activity
        )
        ids.append(message_id)
        print(f"{i}. Time '{time_str}': {message_id[:12]}...")
    
    # Check if all IDs are the same (they should be!)
    all_same = all(id == ids[0] for id in ids)
    print(f"\nAll IDs identical: {'✅ YES (no false notifications)' if all_same else '❌ NO (will spam notifications)'}")
    
    print("\n" + "-" * 50)
    print("Scenario: Actual new activity (new reply author)")
    
    # Now simulate actual new activity
    new_reply_id = scraper._generate_message_id(
        title=thread_title,
        author=original_author,
        forum=forum,
        time_posted='4 мин',  # Even earlier time
        url=thread_url,
        last_reply_author='NewUser'  # NEW: Different last reply author
    )
    
    print(f"New activity detected: {new_reply_id[:12]}...")
    is_different = new_reply_id != ids[0]
    print(f"Different from stable ID: {'✅ YES (new activity detected)' if is_different else '❌ NO (missed new activity)'}")
    
    print("\n" + "=" * 80)
    
    if all_same and is_different:
        print("✅ Perfect! Bot will:")
        print("  • NOT spam for time drift (same thread state)")
        print("  • WILL notify for new replies (different last_reply_author)")
        return True
    else:
        print("❌ Issues detected:")
        if not all_same:
            print("  • Time drift causes false notifications")
        if not is_different:
            print("  • New activity not detected")
        return False

if __name__ == "__main__":
    success = test_time_drift_resistance()
    if success:
        print("\n🎉 Time drift issue resolved!")
    else:
        print("\n❌ Time drift issue persists!")