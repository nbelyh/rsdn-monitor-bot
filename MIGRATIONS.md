# Database Migration System

## Overview
The RSDN Bot uses an automatic migration system to safely update the database schema in production without manual intervention. Migrations run automatically on application startup in both local and Azure environments.

## How It Works

### Migration Tracking
- A `schema_migrations` table tracks which migrations have been applied
- Each migration has a unique version number and runs exactly once
- Migrations are applied in order, skipping already-applied ones
- Safe to run on every application startup

### Automatic Execution
**Local Development:**
```bash
python main.py  # Migrations run automatically before bot starts
```

**Azure App Service:**
- Migrations run automatically when the app starts via `app.py`
- No manual intervention needed when deploying schema changes
- Logged in Azure App Service logs for audit trail

**Manual Execution (optional):**
```bash
python migrations.py  # Run migrations directly
```

## Migration Files

### migrations.py
Contains the `MigrationManager` class and all migration definitions.

**Structure:**
```python
def get_migrations(self) -> List[Tuple[int, str, Callable, str]]:
    return [
        (1, "fix_chat_preferences_pk", 
         self._migration_001_fix_chat_preferences,
         "Fix PRIMARY KEY to allow multiple blocked forums per chat"),
        # Add new migrations here...
    ]
```

## Adding New Migrations

### 1. Create Migration Function
Add a new method to `MigrationManager` class in `migrations.py`:

```python
def _migration_002_your_migration_name(self, conn: sqlite3.Connection):
    """
    Migration 002: Brief description
    Detailed explanation of what this migration does.
    """
    cursor = conn.cursor()
    
    # Your migration SQL here
    cursor.execute("""
        ALTER TABLE some_table 
        ADD COLUMN new_column TEXT
    """)
    
    logger.info("   ✅ Migration logic completed")
```

### 2. Register Migration
Add the migration to the `get_migrations()` list:

```python
def get_migrations(self):
    return [
        (1, "fix_chat_preferences_pk", 
         self._migration_001_fix_chat_preferences,
         "Fix PRIMARY KEY to allow multiple blocked forums per chat"),
        
        (2, "your_migration_name",      # <- New migration
         self._migration_002_your_migration_name,
         "Brief description of changes"),
    ]
```

### 3. Test Locally
```bash
# Test on local database
python migrations.py

# Verify migration was applied
python -c "import sqlite3; conn = sqlite3.connect('rsdn_messages.db'); \
cursor = conn.cursor(); cursor.execute('SELECT * FROM schema_migrations'); \
[print(row) for row in cursor.fetchall()]"
```

### 4. Deploy
```bash
git add migrations.py
git commit -m "Add migration 002: your_migration_name"
git push azure master
```

The migration will run automatically on Azure when the app starts.

## Migration Best Practices

### ✅ DO:
- **Always increment version numbers** (1, 2, 3, ...)
- **Test locally first** before deploying
- **Backup data** when dropping tables (see migration 001 example)
- **Use descriptive names** for migrations
- **Add logging** to track progress
- **Handle missing tables** gracefully (check if exists)
- **Use transactions** (automatic via `with sqlite3.connect()`)

### ❌ DON'T:
- **Never modify existing migrations** after they're deployed
- **Don't skip version numbers**
- **Don't assume table structure** without checking
- **Don't use destructive operations** without backing up data

## Example Migration Patterns

### Adding a Column
```python
def _migration_00X_add_column(self, conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        ALTER TABLE table_name 
        ADD COLUMN new_column TEXT DEFAULT 'default_value'
    """)
```

### Changing PRIMARY KEY (Complex)
```python
def _migration_00X_change_pk(self, conn: sqlite3.Connection):
    cursor = conn.cursor()
    
    # Backup data
    cursor.execute("SELECT * FROM old_table")
    data = cursor.fetchall()
    
    # Drop and recreate
    cursor.execute("DROP TABLE old_table")
    cursor.execute("""
        CREATE TABLE old_table (
            col1 TEXT,
            col2 TEXT,
            PRIMARY KEY (col1, col2)  -- New PK
        )
    """)
    
    # Restore data
    cursor.executemany("INSERT INTO old_table VALUES (?, ?)", data)
```

### Creating a New Table
```python
def _migration_00X_create_table(self, conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS new_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
```

### Adding an Index
```python
def _migration_00X_add_index(self, conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_column_name 
        ON table_name(column_name)
    """)
```

## Monitoring Migrations

### Check Current Version
```bash
python -c "from migrations import MigrationManager; \
m = MigrationManager('rsdn_messages.db'); \
print(f'Current version: {m.get_current_version()}')"
```

### View Migration History
```bash
python -c "import sqlite3; \
conn = sqlite3.connect('rsdn_messages.db'); \
cursor = conn.cursor(); \
cursor.execute('SELECT version, name, applied_at FROM schema_migrations ORDER BY version'); \
print('Migration History:'); \
[print(f'  v{row[0]}: {row[1]} (applied {row[2]})') for row in cursor.fetchall()]"
```

### Azure Logs
Check Azure App Service logs to see migration execution:
```bash
az webapp log tail --name your-app-name --resource-group your-rg
```

Look for log entries like:
```
🚀 Starting database migration check...
📊 Current database schema version: 1
✅ Database schema is up to date
```

## Existing Migrations

### Migration 001: Fix chat_preferences PRIMARY KEY
**Version:** 1  
**Applied:** 2025-09-30  
**Purpose:** Changed PRIMARY KEY from `(chat_id, preference_key)` to `(chat_id, preference_key, preference_value)` to allow multiple blocked forums per chat.

**Changes:**
- Backs up all existing chat preferences
- Drops and recreates `chat_preferences` table
- Updates PRIMARY KEY constraint
- Restores all data with deduplication (`INSERT OR IGNORE`)

## Troubleshooting

### Migration Failed on Azure
1. Check Azure logs for error messages
2. SSH into Azure container: `az webapp ssh --name your-app`
3. Check database: `sqlite3 /home/rsdn_messages.db`
4. View migrations: `SELECT * FROM schema_migrations;`

### Migration Applied Locally but Not on Azure
- Ensure database file on Azure is writable
- Check Azure App Service logs for permission errors
- Verify `DATABASE_FILE` environment variable matches

### Need to Rollback
SQLite doesn't support easy rollbacks. Options:
1. **Best:** Write a new migration to undo changes
2. **Emergency:** Restore from database backup
3. **Fresh start:** Delete `rsdn_messages.db` on Azure (loses all data)

## Database Backup Before Major Changes

Before deploying risky migrations:

```bash
# Local backup
cp rsdn_messages.db rsdn_messages.db.backup

# Azure backup (via Azure Storage or download first)
az webapp download --name your-app --resource-group your-rg \
  --src-path /home/rsdn_messages.db --dest rsdn_messages.azure.backup.db
```
