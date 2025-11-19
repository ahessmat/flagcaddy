# Bug Fix: Domain Filtering False Positives

## Issue

FlagCaddy was detecting non-domain strings as hosts, including:
- File extensions: `flagcaddy.egg`, `README.md`, `package.json`
- Git config keys: `user.name`, `user.email`, `credential.helper`
- Config patterns: `config.yaml`, `settings.ini`

This caused:
- Unnecessary LLM analysis of invalid targets
- Cluttered dashboard with false entities
- Wasted API quota on analyzing files

## Root Cause

The domain validation in `rules.py` was too permissive:
```python
# OLD - Too simple
def _is_valid_domain(self, domain: str) -> bool:
    excluded = ['.txt', '.log', '.json', '.xml', '.html', '.js', '.css', '.py', '.sh']
    if any(domain.endswith(ext) for ext in excluded):
        return False
    if len(domain) < 4:
        return False
    return True
```

It only checked for a small list of file extensions and minimum length.

## Solution

Implemented comprehensive domain validation:

### 1. Extensive File Extension Filtering
Added 40+ file extensions:
- Documents: `.md`, `.rst`, `.yaml`, `.toml`, `.ini`, `.conf`
- Images: `.jpg`, `.png`, `.gif`, `.svg`, `.ico`, `.pdf`
- Archives: `.zip`, `.tar`, `.gz`
- Binaries: `.exe`, `.dll`, `.so`, `.bin`
- Python: `.egg`, `.whl`, `.pyc`, `.pyo`
- And many more...

### 2. Git Config Pattern Filtering
Specific patterns that are common in git operations:
- `user.name`, `user.email`
- `credential.helper`
- `core.editor`, `core.autocrlf`
- `remote.origin`, `branch.main`
- And more...

### 3. Config Pattern Detection
Filters out patterns like:
- `config.*`
- `settings.*`
- `package.*`

### 4. TLD Validation
- Must be at least 2 characters, all letters
- Whitelisted common TLDs (com, org, net, edu, io, etc.)
- Pentest/CTF TLDs: htb, thm, ctf, box, local
- Non-standard TLDs require at least 3 domain parts

### 5. RFC Compliance
- Each label max 63 characters
- No leading/trailing hyphens
- Valid characters only (letters, numbers, hyphens)
- Overall max 253 characters

### 6. Version Number Detection
Filters out patterns like `1.2.3` that look like version numbers

## New Validation Logic

```python
def _is_valid_domain(self, domain: str) -> bool:
    # 1. Length check (4-253 chars)
    # 2. File extension filtering (40+ extensions)
    # 3. Git config pattern filtering
    # 4. Config pattern detection
    # 5. TLD validation (must be valid TLD or 3+ parts)
    # 6. RFC-compliant label validation
    # 7. Version number filtering
    return True/False
```

## Testing

All test cases pass:

**False Positives (correctly rejected):**
- ✅ `flagcaddy.egg`
- ✅ `credential.helper`
- ✅ `user.name`
- ✅ `user.email`
- ✅ `README.md`
- ✅ `config.yaml`
- ✅ `package.json`
- ✅ `test.log`
- ✅ `1.2.3`
- ✅ `file.py`

**True Positives (correctly accepted):**
- ✅ `example.com`
- ✅ `google.com`
- ✅ `target.htb`
- ✅ `api.example.com`
- ✅ `mail.google.com`
- ✅ `test.ctf`
- ✅ `192.168.1.10.nip.io`

## Cleanup Command

New CLI command to remove existing false positives:

```bash
flagcaddy cleanup
```

This will:
1. Scan all host entities in the database
2. Re-validate each one with the new strict rules
3. Remove invalid entities and their:
   - Entity-command links
   - Associated analysis
   - Database entries

Example output:
```
Cleaning up false positive entities...
  Removed: flagcaddy.egg
  Removed: credential.helper
  Removed: user.name
  Removed: user.email
  Removed: README.md

Cleanup complete:
  Removed: 5 false positives
  Kept: 3 valid hosts
```

## Usage

### For New Installs
The fix is already active - no action needed.

### For Existing Installs
If you already have false positive entities:

```bash
# Stop FlagCaddy if running
# Ctrl+C in the FlagCaddy terminal

# Run cleanup
source venv/bin/activate
flagcaddy cleanup

# Restart
flagcaddy start
```

## Impact

- **Reduced false positives**: Only real domains/hosts tracked
- **Cleaner dashboard**: No more file extensions showing as hosts
- **Saved LLM quota**: No analysis of invalid entities
- **Better recommendations**: AI focuses on actual targets

## Files Changed

1. **`flagcaddy/rules.py`**
   - Enhanced `_is_valid_domain()` method
   - Added comprehensive filtering logic

2. **`flagcaddy/cli.py`**
   - Added `cleanup` command
   - Removes false positive entities from database

## Future Improvements

Potential enhancements:
- [ ] Machine learning to identify domain patterns
- [ ] User-configurable whitelist/blacklist
- [ ] Auto-cleanup on startup
- [ ] Domain reputation checking
- [ ] Wildcard pattern support
