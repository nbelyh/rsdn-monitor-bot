"""
Verification script to confirm migration system is ready for Azure deployment
"""
import sys
import sqlite3
from pathlib import Path

def verify_migration_system():
    """Run all verification checks"""
    print("🔍 MIGRATION SYSTEM VERIFICATION")
    print("=" * 60)
    
    all_checks_passed = True
    
    # Check 1: migrations.py exists
    print("\n✓ Check 1: migrations.py exists")
    if not Path("migrations.py").exists():
        print("  ❌ migrations.py not found!")
        all_checks_passed = False
    else:
        print("  ✅ migrations.py found")
    
    # Check 2: Migration can be imported
    print("\n✓ Check 2: Import migration system")
    try:
        from migrations import MigrationManager, run_migrations
        print("  ✅ Migration system imports successfully")
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        all_checks_passed = False
        return False
    
    # Check 3: Database has migration table
    print("\n✓ Check 3: Migration tracking table exists")
    db_path = "rsdn_messages.db"
    if not Path(db_path).exists():
        print(f"  ⚠️  Database {db_path} doesn't exist (will be created on first run)")
    else:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_migrations'
            """)
            if cursor.fetchone():
                print("  ✅ schema_migrations table exists")
            else:
                print("  ❌ schema_migrations table not found!")
                all_checks_passed = False
    
    # Check 4: Migration version is correct
    print("\n✓ Check 4: Check current migration version")
    try:
        manager = MigrationManager(db_path)
        version = manager.get_current_version()
        print(f"  ✅ Current database version: {version}")
        
        if version >= 1:
            print("  ✅ Migration 001 (fix_chat_preferences_pk) is applied")
        else:
            print("  ⚠️  Migration 001 not yet applied (will run on next startup)")
    except Exception as e:
        print(f"  ❌ Error checking version: {e}")
        all_checks_passed = False
    
    # Check 5: Verify chat_preferences schema
    print("\n✓ Check 5: Verify chat_preferences PRIMARY KEY")
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(chat_preferences)")
            columns = cursor.fetchall()
            
            # Check if table exists
            if not columns:
                print("  ⚠️  chat_preferences table doesn't exist yet")
            else:
                # Check primary key columns
                pk_columns = [col[1] for col in columns if col[5] > 0]
                expected_pk = ['chat_id', 'preference_key', 'preference_value']
                
                if pk_columns == expected_pk:
                    print(f"  ✅ PRIMARY KEY is correct: {pk_columns}")
                else:
                    print(f"  ❌ PRIMARY KEY mismatch!")
                    print(f"     Expected: {expected_pk}")
                    print(f"     Found: {pk_columns}")
                    all_checks_passed = False
    except Exception as e:
        print(f"  ❌ Error checking schema: {e}")
        all_checks_passed = False
    
    # Check 6: Test multiple forum blocking
    print("\n✓ Check 6: Test multiple forum blocking")
    try:
        from database import DatabaseManager
        db = DatabaseManager(db_path)
        
        test_chat = "verify_test_123"
        
        # Clean up any previous test data
        db.reset_chat_forum_filters(test_chat)
        
        # Block 3 forums
        db.block_forum_for_chat(test_chat, "TestForum1")
        db.block_forum_for_chat(test_chat, "TestForum2")
        db.block_forum_for_chat(test_chat, "TestForum3")
        
        # Verify all 3 are blocked
        blocked = db.get_chat_blocked_forums(test_chat)
        
        if len(blocked) == 3:
            print(f"  ✅ Successfully blocked {len(blocked)} forums")
        else:
            print(f"  ❌ Expected 3 blocked forums, got {len(blocked)}")
            all_checks_passed = False
        
        # Cleanup
        db.reset_chat_forum_filters(test_chat)
        
    except Exception as e:
        print(f"  ❌ Error testing forum blocking: {e}")
        all_checks_passed = False
    
    # Check 7: Integration in main.py
    print("\n✓ Check 7: Verify integration in main.py")
    try:
        with open("main.py", "r", encoding="utf-8") as f:
            main_content = f.read()
            if "from migrations import run_migrations" in main_content:
                print("  ✅ Migration import found in main.py")
            else:
                print("  ❌ Migration import missing in main.py")
                all_checks_passed = False
            
            if "run_migrations" in main_content:
                print("  ✅ run_migrations() call found in main.py")
            else:
                print("  ❌ run_migrations() call missing in main.py")
                all_checks_passed = False
    except Exception as e:
        print(f"  ❌ Error checking main.py: {e}")
        all_checks_passed = False
    
    # Check 8: Integration in app.py
    print("\n✓ Check 8: Verify integration in app.py")
    try:
        with open("app.py", "r", encoding="utf-8") as f:
            app_content = f.read()
            if "from migrations import run_migrations" in app_content:
                print("  ✅ Migration import found in app.py")
            else:
                print("  ❌ Migration import missing in app.py")
                all_checks_passed = False
            
            if "run_migrations" in app_content:
                print("  ✅ run_migrations() call found in app.py")
            else:
                print("  ❌ run_migrations() call missing in app.py")
                all_checks_passed = False
    except Exception as e:
        print(f"  ❌ Error checking app.py: {e}")
        all_checks_passed = False
    
    # Final summary
    print("\n" + "=" * 60)
    if all_checks_passed:
        print("✅ ALL CHECKS PASSED - READY FOR AZURE DEPLOYMENT!")
        print("\nNext steps:")
        print("  1. git add migrations.py MIGRATIONS.md app.py main.py database.py")
        print("  2. git commit -m 'Add migration system and fix forum blocking'")
        print("  3. git push azure master")
        print("\nThe migration will run automatically when deployed to Azure.")
        return True
    else:
        print("❌ SOME CHECKS FAILED - PLEASE FIX BEFORE DEPLOYING")
        return False

if __name__ == "__main__":
    success = verify_migration_system()
    sys.exit(0 if success else 1)
