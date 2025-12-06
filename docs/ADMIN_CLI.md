# FlowDash Admin CLI

Command-line interface for managing FlowDash backend administration tasks.

## Overview

The Admin CLI provides tools for managing user tester status, resetting quotas, and other administrative functions. It uses Click for command-line argument parsing and connects directly to the database.

## Prerequisites

- Python 3.11+
- Database connection configured in `.env` file
- All dependencies installed (`pip install -r requirements.txt`)

## Running the CLI

### Recommended Method: Run as a Module

The recommended way to run the CLI is as a Python module from the project root:

```bash
python -m app.cli.admin <command> [options]
```

This method works regardless of your current directory and properly resolves package imports.

### Alternative Methods

#### Method 1: Set PYTHONPATH

```bash
# From project root
PYTHONPATH=. python app/cli/admin.py <command> [options]

# Or export it first
export PYTHONPATH=.
python app/cli/admin.py <command> [options]
```

#### Method 2: Direct Execution (if PYTHONPATH is set)

```bash
python app/cli/admin.py <command> [options]
```

### Running Inside Docker Container

If running inside a Docker container:

```bash
# Method 1: As module (recommended)
python -m app.cli.admin <command> [options]

# Method 2: With PYTHONPATH
export PYTHONPATH=/app
python /app/app/cli/admin.py <command> [options]
```

## Available Commands

### `tester` - Manage Tester Status

Manages tester status for users. Testers have access to beta features and early releases.

#### Command Options

- `--email <email>`: User email address
- `--id <user_id>`: User ID (Firebase UID)
- `--set`: Set tester status (flag)
- `--remove`: Remove tester status (flag)
- `--list`: List all testers (flag)

#### Usage Examples

**List all testers:**
```bash
python -m app.cli.admin tester --list
```

**Set tester status by email:**
```bash
python -m app.cli.admin tester --email user@example.com --set
```

**Set tester status by Firebase UID:**
```bash
python -m app.cli.admin tester --id firebase-uid-here --set
```

**Remove tester status by email:**
```bash
python -m app.cli.admin tester --email user@example.com --remove
```

**Remove tester status by Firebase UID:**
```bash
python -m app.cli.admin tester --id firebase-uid-here --remove
```

**Check tester status:**
```bash
python -m app.cli.admin tester --email user@example.com
# or
python -m app.cli.admin tester --id firebase-uid-here
```

---

### `reset-quota` - Reset User Quotas

Resets quota counts for a user by setting counts to 0. Useful for testers or support scenarios where a user's daily quota needs to be restored.

#### Command Options

- `--email <email>`: User email address
- `--id <user_id>`: User ID (Firebase UID)
- `--quota-type <type>`: Specific quota type to reset (`toggles`, `refreshes`, `error_views`). If omitted, resets all types.
- `--date <YYYY-MM-DD>`: Target date for reset. Defaults to today.
- `--yes`: Skip confirmation prompt
- `--dry-run`: Show what would be changed without committing

#### Usage Examples

**Dry-run (preview changes without committing):**
```bash
python -m app.cli.admin reset-quota --email user@example.com --dry-run
```

**Reset all quotas for a user (with confirmation):**
```bash
python -m app.cli.admin reset-quota --email user@example.com
```

**Reset all quotas for a user (skip confirmation):**
```bash
python -m app.cli.admin reset-quota --email user@example.com --yes
```

**Reset only toggles quota:**
```bash
python -m app.cli.admin reset-quota --email user@example.com --quota-type toggles --yes
```

**Reset quotas for a specific date:**
```bash
python -m app.cli.admin reset-quota --email user@example.com --date 2025-12-01 --yes
```

**Reset by Firebase UID:**
```bash
python -m app.cli.admin reset-quota --id firebase-uid-here --yes
```

#### Example Output

**Dry-run output:**
```
🔍 Dry run: would Reset quotas for user@example.com on 2025-12-02
Found 3 quota rows that would be reset:
  - type: toggles, count: 5, date: 2025-12-02
  - type: refreshes, count: 12, date: 2025-12-02
  - type: error_views, count: 3, date: 2025-12-02
```

**Successful reset:**
```
✓ Reset 3 quota rows for user@example.com
```

**No quota rows found:**
```
No quota rows would be affected
```

---

## Important Notes

1. **For non-list operations**, you must provide either `--email` or `--id`
2. **Tester limit**: Maximum of 100 testers (enforced when setting tester status)
3. **Quota types**: Valid types are `toggles`, `refreshes`, `error_views`
4. **Database connection**: The CLI connects to the database using `SessionLocal()` from your database configuration
5. **Environment**: Ensure your `.env` file is configured with the correct `DATABASE_URL` before running

## Output Messages

The CLI provides clear feedback for each operation:

- ✓ Success messages indicate successful operations
- ❌ Error messages indicate failures or issues
- 🔍 Dry-run messages show what would happen without making changes
- Status messages show current state without making changes

### Example Output

**Listing testers:**
```
Found 3 testers:

  - user1@example.com (ID: abc123, Plan: pro)
  - user2@example.com (ID: def456, Plan: free)
  - <no-email> (ID: ghi789, Plan: basic)
```

**Setting tester status:**
```
✓ Set tester status for user@example.com
```

**Removing tester status:**
```
✓ Removed tester status for user@example.com
```

**Checking status:**
```
User user@example.com is tester
```

**Error messages:**
```
❌ User not found: user@example.com
❌ Tester limit reached (100)
❌ Please provide --email or --id for this operation
❌ Invalid date format. Use YYYY-MM-DD
```

## Troubleshooting

### ModuleNotFoundError: No module named 'app'

This error occurs when Python cannot find the `app` package. Solutions:

1. **Use module syntax** (recommended):
   ```bash
   python -m app.cli.admin tester --list
   ```

2. **Set PYTHONPATH**:
   ```bash
   PYTHONPATH=. python app/cli/admin.py tester --list
   ```

3. **Run from project root**:
   Make sure you're in the directory containing the `app/` folder.

### Database Connection Errors

If you see database connection errors:

1. Verify `.env` file exists and contains `DATABASE_URL`
2. Ensure the database is running and accessible
3. Check that database credentials are correct
4. Verify network connectivity (if database is remote)

### User Not Found

If you get "User not found" errors:

1. Verify the email or UID is correct
2. Check that the user exists in the database
3. Ensure you're connected to the correct database

## Command Reference

### Quick Reference

```bash
# === TESTER MANAGEMENT ===

# List all testers
python -m app.cli.admin tester --list

# Set tester (by email)
python -m app.cli.admin tester --email <email> --set

# Set tester (by ID)
python -m app.cli.admin tester --id <uid> --set

# Remove tester (by email)
python -m app.cli.admin tester --email <email> --remove

# Remove tester (by ID)
python -m app.cli.admin tester --id <uid> --remove

# Check status (by email)
python -m app.cli.admin tester --email <email>

# Check status (by ID)
python -m app.cli.admin tester --id <uid>

# === QUOTA MANAGEMENT ===

# Dry-run (preview reset)
python -m app.cli.admin reset-quota --email <email> --dry-run

# Reset all quotas (with confirmation)
python -m app.cli.admin reset-quota --email <email>

# Reset all quotas (skip confirmation)
python -m app.cli.admin reset-quota --email <email> --yes

# Reset specific quota type
python -m app.cli.admin reset-quota --email <email> --quota-type toggles --yes

# Reset for specific date
python -m app.cli.admin reset-quota --email <email> --date 2025-12-01 --yes

# Reset by user ID
python -m app.cli.admin reset-quota --id <uid> --yes
```

## Future Commands

Additional administrative commands may be added in the future. Check this documentation for updates.

