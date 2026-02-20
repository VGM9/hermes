#!/bin/bash
# Fix Unicode issues in all HERMES Python files
# M1 Issue #1-3: Unicode Remediation

HERMES_DIR="/c/www/VGM9/_/AS/0.0.Q/_/software/hermes"
cd "$HERMES_DIR"

# List of Python files to fix (excluding already fixed ones)
FILES=(
  "hermes_agent_approval_detection.py"
  "hermes_agent_discovery.py"
  "hermes_approval_decision.py"
  "hermes_approval_log.py"
  "hermes_approval_orchestrator.py"
  "hermes_chat_ops.py"
  "hermes_config.py"
  "hermes_direct_v2.py"
  "hermes_nonce_verify.py"
  "hermes_self_send.py"
  "hermes_session_discovery.py"
  "hermes_session_verify.py"
  "hermes_sessions.py"
  "hermes_wait_send.py"
  "hermes_wake.py"
  "hermes_window_ops.py"
)

echo "Fixing Unicode issues in ${#FILES[@]} HERMES Python files..."echo ""

for file in "${FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "⚠ Skipping $file (not found)"
    continue
  fi
  
  echo "Processing: $file"
  
  # Check if already has UTF-8 header
  if head -n 2 "$file" | grep -q "coding: utf-8"; then
    echo "  ✓ Already has UTF-8 header"
  else
    # Add UTF-8 encoding header after shebang
    if head -n 1 "$file" | grep -q "^#!"; then
      # Has shebang - insert after it
      sed -i '1a # -*- coding: utf-8 -*-' "$file"
      echo "  + Added UTF-8 header after shebang"
    else
      # No shebang - add at top
      sed -i '1i # -*- coding: utf-8 -*-' "$file"
      echo "  + Added UTF-8 header at top"
    fi
  fi
  
  # Check if file has Unicode symbols
  if grep -q "✓\|✗" "$file"; then
    echo "  ! Contains Unicode symbols"
    
    # Check if safe_print already defined
    if grep -q "def safe_print" "$file"; then
      echo "  ✓ safe_print() already defined"
    else
      # Add safe_print function after imports
      # Find last import line
      last_import=$(grep -n "^import\|^from" "$file" | tail -1 | cut -d: -f1)
      if [ -n "$last_import" ]; then
        # Insert safe_print after imports
        sed -i "${last_import}a\\
\\
\\
def safe_print(msg):\\
    \"\"\"Print with fallback for non-UTF8 terminals (Windows cp1252)\"\"\"\\
    try:\\
        print(msg)\\
    except UnicodeEncodeError:\\
        # Replace Unicode symbols with ASCII equivalents\\
        safe_msg = msg.replace('✓', '[OK]').replace('✗', '[FAIL]')\\
        print(safe_msg.encode('ascii', 'replace').decode('ascii'))" "$file"
        echo "  + Added safe_print() function"
      fi
    fi
    
    # Replace print() with safe_print() for Unicode lines
    sed -i 's/print(f"✓/safe_print(f"✓/g' "$file"
    sed -i 's/print(f"✗/safe_print(f"✗/g' "$file"
    sed -i "s/print(f'✓/safe_print(f'✓/g" "$file"
    sed -i "s/print(f'✗/safe_print(f'✗/g" "$file"
    
    # Also check for plain print with Unicode (not f-string)
    sed -i 's/print("✓/safe_print("✓/g' "$file"
    sed -i 's/print("✗/safe_print("✗/g' "$file"
    
    echo "  + Replaced print() with safe_print() for Unicode"
  else
    echo "  ✓ No Unicode symbols found"
  fi
  
  echo ""
done

echo "============================================"
echo "Unicode remediation complete!"
echo "Files processed: ${#FILES[@]}"
echo ""
echo "Next steps:"
echo "1. Test each modified file"
echo "2. git add ."
echo "3. git commit -m 'fix(unicode): Complete M1 Unicode remediation for all HERMES files'"
echo "4. Proceed to M2: Identity Preservation"
