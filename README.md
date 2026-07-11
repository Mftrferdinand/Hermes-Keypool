# Hermes API Key Pool Manager

A standalone Python script to manage API key pools in [Hermes Agent](https://github.com/NousResearch/hermes-agent)'s credential system. Add, list, and reset API keys for any provider — Hermes handles auto-rotation automatically once keys are in the pool.

## Features

- **Add multiple keys** to any provider's credential pool
- **Replace or append** mode — overwrite existing keys or add to the pool
- **List all keys** across all providers or filter by specific provider
- **Reset exhausted keys** — clear error status to retry rate-limited keys
- **Duplicate detection** — skips keys already in the pool
- **Backup** — automatically backs up `auth.json` before modifying
- **No dependencies** — pure Python 3, no pip installs needed
- **Works with any provider** — OpenRouter, OpenAI, custom endpoints, anything Hermes supports

## Quick Start

```bash
# Add keys (comma-separated)
python3 hermes-keypool.py \
  --provider "custom:api.aiand.com" \
  --base-url "https://api.aiand.com/v1" \
  --keys "sk-key1,sk-key2,sk-key3"

# Add keys from file (one per line)
python3 hermes-keypool.py \
  --provider "custom:api.aiand.com" \
  --base-url "https://api.aiand.com/v1" \
  --file keys.txt

# Pipe keys via stdin
echo -e "sk-key1\nsk-key2\nsk-key3" | python3 hermes-keypool.py \
  --provider "custom:api.aiand.com" \
  --base-url "https://api.aiand.com/v1"

# Interactive mode (prompts for everything)
python3 hermes-keypool.py
```

After adding keys, restart Hermes:

```
# Gateway (Telegram, Discord, etc.)
/restart

# CLI
exit and relaunch
```

## Usage

```
usage: hermes-keypool.py [-h] [--provider PROVIDER] [--base-url BASE_URL]
                         [--keys KEYS] [--file FILE] [--append]
                         [--list] [--reset RESET] [--interactive]

optional arguments:
  --provider, -p    Provider name (e.g. "custom:api.aiand.com")
  --base-url, -u    API base URL (e.g. https://api.aiand.com/v1)
  --keys, -k        Comma-separated API keys
  --file, -f        File containing API keys (one per line)
  --append, -a      Append to existing pool (default: replace)
  --list, -l        List all keys in pool
  --reset, -r       Reset exhausted status for a provider
  --interactive, -i  Interactive mode
```

## How It Works

Hermes Agent stores credentials in `~/.hermes/auth.json` under a `credential_pool` keyed by provider name. When a key hits a rate limit (429, 402, 403), Hermes automatically rotates to the next key in the pool.

This script writes directly to that file — no Hermes restart needed to apply changes during a session, but a restart ensures the pool is reloaded cleanly.

### Provider Names

| Provider Type | Example |
|---|---|
| Custom endpoint | `custom:api.aiand.com` |
| OpenRouter | `openrouter` |
| OpenAI | `openai-api` |
| NVIDIA | `nvidia` |
| Google Gemini | `google` |
| Z.AI / GLM | `zai` |

### Modes

- **Replace (default)** — Removes manually-added keys, keeps config-sourced keys, adds new ones
- **Append (`--append`)** — Keeps all existing keys, adds new ones at the end

## Examples

```bash
# List all keys across all providers
python3 hermes-keypool.py --list

# List keys for a specific provider
python3 hermes-keypool.py --list --provider "custom:api.aiand.com"

# Reset all exhausted keys for a provider
python3 hermes-keypool.py --reset "custom:api.aiand.com"

# Append keys without replacing existing ones
python3 hermes-keypool.py \
  -p "custom:api.aiand.com" \
  -u "https://api.aiand.com/v1" \
  -k "sk-newkey" \
  --append
```

## Use with AI Agents

This script is designed to be run by AI agents (like Hermes) — just give the agent your list of API keys and the provider details, and it can run the script for you:

```
User: "Add these keys to my Hermes pool: sk-aaa, sk-bbb, sk-ccc"

Agent: python3 hermes-keypool.py \
  --provider "custom:api.aiand.com" \
  --base-url "https://api.aiand.com/v1" \
  --keys "sk-aaa,sk-bbb,sk-ccc"
```

## Requirements

- Python 3.6+
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed (`~/.hermes/auth.json` must exist)

## License

[MIT License](LICENSE) — free to use, modify, and distribute.
