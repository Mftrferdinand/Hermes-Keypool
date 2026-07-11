#!/usr/bin/env python3
"""
Hermes API Key Pool Manager
Add multiple API keys to Hermes credential pool for auto-rotation.

Usage:
  python3 hermes-keypool.py --provider "custom:api.aiand.com" --base-url "https://api.aiand.com/v1" --keys "sk-key1,sk-key2,sk-key3"

  Or read keys from stdin (one per line):
  echo -e "sk-key1\nsk-key2\nsk-key3" | python3 hermes-keypool.py --provider "custom:api.aiand.com" --base-url "https://api.aiand.com/v1"

  Or read keys from a file:
  python3 hermes-keypool.py --provider "custom:api.aiand.com" --base-url "https://api.aiand.com/v1" --file keys.txt

  Or interactive (will prompt):
  python3 hermes-keypool.py

After adding keys, restart Hermes:
  - Gateway: /restart
  - CLI: exit and relaunch
"""

import argparse
import hashlib
import json
import os
import sys
import time


def get_auth_path():
    """Find Hermes auth.json path."""
    home = os.environ.get("HERMES_HOME", os.path.expanduser("~/.hermes"))
    return os.path.join(home, "auth.json")


def load_auth(path):
    """Load auth.json."""
    if not os.path.exists(path):
        print(f"Error: {path} not found. Is Hermes installed?")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def save_auth(path, auth):
    """Save auth.json with backup."""
    backup = path + ".bak"
    if os.path.exists(path):
        with open(path) as f:
            with open(backup, "w") as bf:
                bf.write(f.read())
    auth["updated_at"] = time.strftime(
        "%Y-%m-%dT%H:%M:%S.000000+00:00", time.gmtime()
    )
    with open(path, "w") as f:
        json.dump(auth, f, indent=2)
    print(f"Backup saved: {backup}")


def fingerprint(key):
    """SHA256 fingerprint of a key."""
    return f"sha256:{hashlib.sha256(key.encode()).hexdigest()[:16]}"


def add_keys(provider, base_url, keys, mode="replace"):
    """Add keys to credential pool.

    mode:
      - replace: remove all existing keys for this provider, add new ones
      - append: keep existing keys, add new ones at the end
    """
    auth_path = get_auth_path()
    auth = load_auth(auth_path)

    pool = auth.get("credential_pool", {})
    existing = pool.get(provider, [])

    if mode == "replace":
        # Keep keys from config (source starts with "config:" or "model_config")
        # those are auto-managed by Hermes, don't touch them
        kept = [e for e in existing if e.get("source", "").startswith("config:") or e.get("source") == "model_config"]
        removed_count = len(existing) - len(kept)
        start_priority = max([e.get("priority", 0) for e in kept], default=-1) + 1
        entries = kept
    else:
        kept = existing
        removed_count = 0
        start_priority = max([e.get("priority", 0) for e in existing], default=-1) + 1
        entries = list(existing)

    added = []
    skipped = 0
    existing_fps = {e.get("secret_fingerprint") for e in entries}

    for i, key in enumerate(keys):
        key = key.strip()
        if not key:
            continue
        fp = fingerprint(key)
        if fp in existing_fps:
            print(f"  Skip duplicate: {key[:8]}...{key[-4:]}")
            skipped += 1
            continue

        entry = {
            "id": fp.replace("sha256:", "")[:6],
            "label": f"key-{start_priority + len(added) + 1}",
            "auth_type": "api_key",
            "priority": start_priority + len(added),
            "source": "manual",
            "access_token": key,
            "last_status": None,
            "last_status_at": None,
            "last_error_code": None,
            "last_error_reason": None,
            "last_error_message": None,
            "last_error_reset_at": None,
            "base_url": base_url,
            "request_count": 0,
            "secret_fingerprint": fp,
        }
        entries.append(entry)
        existing_fps.add(fp)
        added.append(entry)
        print(f"  Added [{entry['priority']}] {key[:8]}...{key[-4:]} ({fp[:20]}...)")

    pool[provider] = entries
    auth["credential_pool"] = pool

    save_auth(auth_path, auth)

    print()
    print(f"Provider:  {provider}")
    print(f"Base URL:  {base_url}")
    print(f"Mode:      {mode}")
    print(f"Added:     {len(added)}")
    print(f"Skipped:   {skipped} (duplicates)")
    print(f"Removed:   {removed_count}")
    print(f"Total pool: {len(entries)} keys")
    print()
    print("Restart Hermes to apply:")
    print("  Gateway: /restart")
    print("  CLI: exit and relaunch")


def list_keys(provider=None):
    """List all keys in credential pool."""
    auth_path = get_auth_path()
    auth = load_auth(auth_path)
    pool = auth.get("credential_pool", {})

    if provider:
        providers = [provider]
    else:
        providers = sorted(pool.keys())

    for p in providers:
        entries = pool.get(p, [])
        if not entries:
            continue
        print(f"\n{p} ({len(entries)} keys)")
        print("-" * 60)
        for e in entries:
            status = e.get("last_status") or "unknown"
            key_preview = e.get("access_token", "")
            if key_preview:
                key_preview = f"{key_preview[:8]}...{key_preview[-4:]}"
            elif e.get("secret_fingerprint", "").startswith("sha256:"):
                key_preview = e["secret_fingerprint"][:20] + "..."
            label = e.get("label", "?")
            print(f"  [{e.get('priority', '?')}] {label:20s} {key_preview:24s} {status}")


def reset_provider(provider):
    """Reset exhausted status for all keys of a provider."""
    auth_path = get_auth_path()
    auth = load_auth(auth_path)
    pool = auth.get("credential_pool", {})
    entries = pool.get(provider, [])

    if not entries:
        print(f"No keys found for {provider}")
        return

    reset_count = 0
    for e in entries:
        if e.get("last_status") == "exhausted":
            e["last_status"] = None
            e["last_error_code"] = None
            e["last_error_reason"] = None
            e["last_error_message"] = None
            e["last_error_reset_at"] = None
            reset_count += 1

    save_auth(auth_path, auth)
    print(f"Reset {reset_count} exhausted keys for {provider}")


def main():
    parser = argparse.ArgumentParser(
        description="Hermes API Key Pool Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add keys (replace mode)
  python3 hermes-keypool.py --provider "custom:api.aiand.com" --base-url "https://api.aiand.com/v1" --keys "sk-aaa,sk-bbb,sk-ccc"

  # Add keys from file
  python3 hermes-keypool.py --provider "custom:api.aiand.com" --base-url "https://api.aiand.com/v1" --file keys.txt

  # Append keys (keep existing)
  python3 hermes-keypool.py --provider "custom:api.aiand.com" --base-url "https://api.aiand.com/v1" --keys "sk-aaa" --append

  # List all keys
  python3 hermes-keypool.py --list

  # List keys for specific provider
  python3 hermes-keypool.py --list --provider "custom:api.aiand.com"

  # Reset exhausted keys
  python3 hermes-keypool.py --reset "custom:api.aiand.com"

  # Interactive mode
  python3 hermes-keypool.py
        """,
    )
    parser.add_argument("--provider", "-p", help='Provider name (e.g. "custom:api.aiand.com")')
    parser.add_argument("--base-url", "-u", help="API base URL (e.g. https://api.aiand.com/v1)")
    parser.add_argument("--keys", "-k", help="Comma-separated API keys")
    parser.add_argument("--file", "-f", help="File containing API keys (one per line)")
    parser.add_argument("--append", "-a", action="store_true", help="Append to existing pool (default: replace)")
    parser.add_argument("--list", "-l", action="store_true", help="List all keys in pool")
    parser.add_argument("--reset", "-r", help="Reset exhausted status for a provider")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")

    args = parser.parse_args()

    # Reset mode
    if args.reset:
        reset_provider(args.reset)
        return

    # List mode
    if args.list:
        list_keys(args.provider)
        return

    # Interactive mode
    if args.interactive or (not args.provider and not args.keys and not args.file):
        print("=== Hermes API Key Pool Manager ===")
        print()
        print("1. Add keys")
        print("2. List keys")
        print("3. Reset exhausted keys")
        print("4. Exit")
        choice = input("\nChoice: ").strip()

        if choice == "2":
            list_keys()
            return
        elif choice == "3":
            provider = input("Provider name (e.g. custom:api.aiand.com): ").strip()
            if provider:
                reset_provider(provider)
            return
        elif choice == "4":
            return
        elif choice != "1":
            print("Invalid choice")
            return

        # Add keys flow
        provider = input("Provider name (e.g. custom:api.aiand.com): ").strip()
        if not provider:
            print("Provider required")
            return

        base_url = input("Base URL (e.g. https://api.aiand.com/v1): ").strip()
        if not base_url:
            print("Base URL required")
            return

        print("\nEnter API keys (one per line, empty line to finish):")
        keys = []
        while True:
            line = input().strip()
            if not line:
                break
            keys.append(line)

        if not keys:
            print("No keys provided")
            return

        mode = "replace"
        add_keys(provider, base_url, keys, mode)
        return

    # CLI mode
    if not args.provider:
        parser.error("--provider required")
    if not args.base_url:
        parser.error("--base-url required")

    # Get keys
    keys = []
    if args.file:
        with open(args.file) as f:
            keys = [line.strip() for line in f if line.strip()]
    elif args.keys:
        keys = [k.strip() for k in args.keys.split(",") if k.strip()]
    else:
        # Read from stdin
        if not sys.stdin.isatty():
            keys = [line.strip() for line in sys.stdin if line.strip()]

    if not keys:
        parser.error("No keys provided. Use --keys, --file, or pipe via stdin")

    mode = "append" if args.append else "replace"
    add_keys(args.provider, args.base_url, keys, mode)


if __name__ == "__main__":
    main()
