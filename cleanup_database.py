#!/usr/bin/env python3
"""Clean up and optimize the RSDN bot database"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from database import DatabaseManager

def cleanup_database():
    """Clean up the database and show statistics"""
    
    db_path = 'rsdn_messages.db'
    
    if not os.path.exists(db_path):
        print(f'❌ Database file {db_path} not found')
        return
    
    print(f'🔧 Cleaning up database: {db_path}')
    print(f'📁 Database size before: {os.path.getsize(db_path) / 1024:.1f} KB')
    
    # Initialize database manager
    db = DatabaseManager(db_path)
    
    # Show current statistics
    print('\n📊 Current database statistics:')
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Total messages
        cursor.execute("SELECT COUNT(*) FROM seen_messages")
        total_messages = cursor.fetchone()[0]
        print(f'   Total messages: {total_messages}')
        
        # Messages by age
        cursor.execute("""
            SELECT 
                COUNT(*) as count,
                CASE 
                    WHEN first_seen > datetime('now', '-1 hour') THEN 'Last hour'
                    WHEN first_seen > datetime('now', '-1 day') THEN 'Last 24 hours'
                    WHEN first_seen > datetime('now', '-7 days') THEN 'Last 7 days'
                    WHEN first_seen > datetime('now', '-30 days') THEN 'Last 30 days'
                    ELSE 'Older than 30 days'
                END as age_group
            FROM seen_messages 
            GROUP BY age_group
            ORDER BY count DESC
        """)
        
        age_stats = cursor.fetchall()
        print('   Messages by age:')
        for count, age_group in age_stats:
            print(f'     {age_group}: {count}')
        
        # User preferences
        cursor.execute("SELECT COUNT(*) FROM user_preferences")
        prefs_count = cursor.fetchone()[0]
        print(f'   User preferences: {prefs_count}')
        
        if prefs_count > 0:
            cursor.execute("""
                SELECT user_id, COUNT(*) as blocked_forums
                FROM user_preferences 
                WHERE preference_key = 'blocked_forum'
                GROUP BY user_id
            """)
            user_prefs = cursor.fetchall()
            print('   Blocked forums by user:')
            for user_id, count in user_prefs:
                print(f'     User {user_id}: {count} blocked forums')
    
    # Ask what to clean up
    print('\n🧹 Cleanup options:')
    print('1. Remove messages older than 30 days')
    print('2. Remove messages older than 7 days') 
    print('3. Remove all messages (keep user preferences)')
    print('4. Reset user preferences only')
    print('5. Full reset (remove everything)')
    print('6. Just optimize database (VACUUM)')
    print('0. Cancel')
    
    try:
        choice = input('\nChoose cleanup option (0-6): ').strip()
        
        if choice == '0':
            print('❌ Cleanup cancelled')
            return
            
        elif choice == '1':
            # Remove messages older than 30 days
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM seen_messages 
                    WHERE first_seen < datetime('now', '-30 days')
                """)
                deleted = cursor.rowcount
                print(f'✅ Deleted {deleted} messages older than 30 days')
                
        elif choice == '2':
            # Remove messages older than 7 days
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM seen_messages 
                    WHERE first_seen < datetime('now', '-7 days')
                """)
                deleted = cursor.rowcount
                print(f'✅ Deleted {deleted} messages older than 7 days')
                
        elif choice == '3':
            # Remove all messages but keep preferences
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM seen_messages")
                deleted = cursor.rowcount
                print(f'✅ Deleted all {deleted} messages (preferences kept)')
                
        elif choice == '4':
            # Reset user preferences only
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM user_preferences")
                deleted = cursor.rowcount
                print(f'✅ Reset {deleted} user preferences')
                
        elif choice == '5':
            # Full reset
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM seen_messages")
                msg_deleted = cursor.rowcount
                cursor.execute("DELETE FROM user_preferences")
                pref_deleted = cursor.rowcount
                print(f'✅ Full reset: deleted {msg_deleted} messages and {pref_deleted} preferences')
                
        elif choice == '6':
            print('🔧 Optimizing database...')
            
        else:
            print('❌ Invalid choice')
            return
        
        # Always optimize at the end
        print('🔧 Optimizing database (VACUUM)...')
        with sqlite3.connect(db_path) as conn:
            conn.execute('VACUUM')
        
        print(f'📁 Database size after: {os.path.getsize(db_path) / 1024:.1f} KB')
        
        # Show final statistics
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_messages")
            final_messages = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM user_preferences")  
            final_prefs = cursor.fetchone()[0]
            
        print(f'\n✅ Cleanup complete!')
        print(f'   Messages remaining: {final_messages}')
        print(f'   User preferences: {final_prefs}')
        
    except KeyboardInterrupt:
        print('\n❌ Cleanup cancelled')
    except Exception as e:
        print(f'❌ Error during cleanup: {e}')

if __name__ == "__main__":
    cleanup_database()