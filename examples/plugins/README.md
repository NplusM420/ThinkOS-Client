# ThinkOS Example Plugins

This directory contains example plugins demonstrating how to extend ThinkOS with custom functionality.

## Available Examples

### 1. Hello World (`hello-world/`)
A simple starter plugin showing:
- Basic plugin structure
- Tool registration
- Using the ThinkOS API
- Lifecycle hooks (on_load, on_unload)

**Tools provided:**
- `greet` - Generate greeting messages
- `count_memories` - Count stored memories
- `search_memories_simple` - Simple memory search

### 2. Weather Tool (`weather-tool/`)
A more advanced plugin demonstrating:
- External API integration
- Network access permission
- Multiple related tools
- Error handling

**Tools provided:**
- `get_weather` - Current weather for a location
- `get_forecast` - Multi-day weather forecast

## Plugin Structure

Every plugin requires at minimum:

```
my-plugin/
├── plugin.json    # Manifest file (required)
└── main.py        # Plugin code (required)
```

### plugin.json Schema

```json
{
  "id": "my-plugin",           // Unique ID (lowercase, hyphens only)
  "name": "My Plugin",         // Display name
  "version": "1.0.0",          // Semantic version
  "description": "...",        // Short description
  "type": "tool",              // tool | provider | ui | integration
  "author": {
    "name": "Your Name",
    "email": "you@example.com",
    "url": "https://example.com"
  },
  "main": "main.py",           // Entry point file
  "permissions": [             // Required permissions
    "read_memories",
    "network_access"
  ],
  "python_dependencies": [],   // pip packages needed
  "min_thinkos_version": "0.5.0"
}
```

### main.py Structure

```python
class Plugin:
    def __init__(self, api):
        self.api = api
    
    async def on_load(self):
        """Called when plugin is enabled."""
        pass
    
    async def on_unload(self):
        """Called when plugin is disabled."""
        pass
    
    def register_tools(self) -> list[dict]:
        """Return list of tool definitions."""
        return [
            {
                "name": "my_tool",
                "description": "What this tool does",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string", "description": "..."}
                    },
                    "required": ["param1"]
                },
                "handler": self.my_tool_handler
            }
        ]
    
    async def my_tool_handler(self, params: dict) -> dict:
        return {"success": True, "result": {...}}
```

## Installation

### From UI
1. Zip your plugin folder
2. Go to Settings → Plugins
3. Click "Install Plugin"
4. Upload the ZIP file

### From API
```bash
# Install from directory
curl -X POST http://localhost:8000/api/plugins/install \
  -H "Content-Type: application/json" \
  -d '{"source": "/path/to/plugin", "enable": true}'

# Upload ZIP file
curl -X POST http://localhost:8000/api/plugins/upload \
  -F "file=@my-plugin.zip" \
  -F "enable=true"
```

## Available Permissions

| Permission | Description | Risk Level |
|------------|-------------|------------|
| `read_memories` | Read and search memories | Low |
| `write_memories` | Create/modify memories | Medium |
| `read_settings` | Read app settings | Low |
| `write_settings` | Modify app settings | Medium |
| `execute_tools` | Run other tools | Medium |
| `network_access` | Make HTTP requests | High |
| `file_system` | File read/write | High |
| `agent_execution` | Run AI agents | High |

## Plugin API Reference

### Memory Operations
```python
# Requires: read_memories
memories = await api.get_memories(limit=50, offset=0, tags=["tag1"])
results = await api.search_memories("query", limit=10)

# Requires: write_memories
memory = await api.create_memory(
    title="Title",
    content="Content",
    memory_type="note",
    tags=["tag1", "tag2"]
)
```

### Settings
```python
# Requires: read_settings
value = await api.get_setting("key")

# Requires: write_settings
await api.set_setting("key", "value")
```

### Network
```python
# Requires: network_access
response = await api.http_request(
    method="GET",
    url="https://api.example.com/data",
    headers={"Authorization": "Bearer token"},
    body=None,
    timeout=30.0
)
# response = {"status_code": 200, "headers": {...}, "body": "..."}
```

### Tools
```python
# Requires: execute_tools
result = await api.execute_tool("tool_name", {"param": "value"})
```

### AI
```python
# Always available
response = await api.chat_completion(
    messages=[{"role": "user", "content": "Hello"}],
    model=None,  # Uses default model
    temperature=0.7
)
```

### Logging
```python
# Always available
api.log("info", "Message")    # debug, info, warning, error
```

## Plugin Types

### Tool Plugins (`type: "tool"`)
Add new tools that agents can use. Most common plugin type.

### Provider Plugins (`type: "provider"`)
Add new AI model providers. Implement `register_providers()`:
```python
def register_providers(self) -> list[dict]:
    return [{
        "name": "my-provider",
        "display_name": "My Provider",
        "description": "Custom AI provider",
        "supports_chat": True,
        "supports_embeddings": False,
        "supports_streaming": True,
        "config_schema": {...}
    }]
```

### UI Plugins (`type: "ui"`)
Add new UI routes/pages. Implement `register_routes()`:
```python
def register_routes(self) -> list[dict]:
    return [{
        "path": "/my-page",
        "component": "MyComponent",
        "title": "My Page",
        "icon": "Wrench"
    }]
```

### Integration Plugins (`type: "integration"`)
Connect external services (webhooks, sync, etc.).

## Best Practices

1. **Request minimal permissions** - Only ask for what you need
2. **Handle errors gracefully** - Always return `{"success": False, "error": "..."}` on failure
3. **Use logging** - Help users debug issues with `api.log()`
4. **Document your plugin** - Include a README.md
5. **Version properly** - Use semantic versioning
6. **Test thoroughly** - Test with the plugin enabled and disabled

## Troubleshooting

### Plugin won't load
- Check the plugin.json is valid JSON
- Verify main.py has a `Plugin` class
- Check logs for error messages

### Permission denied
- Add the required permission to plugin.json
- User must re-enable the plugin after permission changes

### API calls failing
- Verify you have the correct permission
- Check network connectivity for HTTP requests
- Review error messages in logs
