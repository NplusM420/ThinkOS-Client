# Hello World Plugin

A simple example plugin demonstrating the ThinkOS plugin system.

## Features

This plugin provides three example tools:

1. **greet** - Generate a friendly greeting message
2. **count_memories** - Count total memories in ThinkOS
3. **search_memories_simple** - Search memories with a simple query

## Installation

### Option 1: Install from directory

1. Copy this folder to your ThinkOS plugins directory
2. Or use the API to install from path:
   ```bash
   curl -X POST http://localhost:8000/api/plugins/install \
     -H "Content-Type: application/json" \
     -d '{"source": "/path/to/hello-world", "enable": true}'
   ```

### Option 2: Install from ZIP

1. Zip this folder: `zip -r hello-world.zip hello-world/`
2. Upload via the ThinkOS UI (Settings → Plugins → Install Plugin)
3. Or use the API:
   ```bash
   curl -X POST http://localhost:8000/api/plugins/upload \
     -F "file=@hello-world.zip" \
     -F "enable=true"
   ```

## Usage

Once installed and enabled, agents can use these tools:

```
Agent: I'll greet you using the hello-world plugin.
[Calls greet tool with name="User" style="enthusiastic"]
Result: WOW! User! SO GREAT to see you! 🎉
```

## Plugin Structure

```
hello-world/
├── plugin.json    # Plugin manifest (required)
├── main.py        # Plugin code (required)
└── README.md      # Documentation (optional)
```

## Creating Your Own Plugin

1. **Create plugin.json** - Define metadata, permissions, and dependencies
2. **Create main.py** - Implement the Plugin class with:
   - `__init__(self, api)` - Initialize with ThinkOS API
   - `on_load()` - Called when plugin is enabled
   - `on_unload()` - Called when plugin is disabled
   - `register_tools()` - Return list of tool definitions

### Available Permissions

| Permission | Description |
|------------|-------------|
| `read_memories` | Access and search memories |
| `write_memories` | Create and modify memories |
| `read_settings` | Read application settings |
| `write_settings` | Modify application settings |
| `execute_tools` | Run other registered tools |
| `network_access` | Make HTTP requests |
| `file_system` | Read/write files |
| `agent_execution` | Run AI agents |

### Plugin API Methods

```python
# Memory operations (requires read_memories/write_memories)
await api.get_memories(limit=50, offset=0, tags=None)
await api.create_memory(title, content, memory_type="note", tags=None)
await api.search_memories(query, limit=10)

# Settings (requires read_settings/write_settings)
await api.get_setting(key)
await api.set_setting(key, value)

# Tools (requires execute_tools)
await api.execute_tool(tool_name, parameters)

# HTTP (requires network_access)
await api.http_request(method, url, headers=None, body=None, timeout=30.0)

# AI (always available)
await api.chat_completion(messages, model=None, temperature=0.7)

# Logging (always available)
api.log(level, message)  # level: "debug", "info", "warning", "error"
```

## License

Apache-2.0
