# ThinkOS

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue.svg)](https://github.com/ai-layer-labs/thinkos)
[![Version](https://img.shields.io/badge/Version-0.5.3-green.svg)](https://github.com/ai-layer-labs/thinkos/releases)

**Your AI-powered personal knowledge assistant and autonomous agent platform.**

ThinkOS is a local-first, privacy-preserving AI operating system that combines personal knowledge management with autonomous AI agents. Save web content, chat with your memories, and deploy AI agents that work on your behalf.

> **Fork Note**: This fork includes additional features like Browser Automation, Voice/Multi-modal support, and enhanced Agent Studio capabilities. See [Fork Enhancements](#-fork-enhancements) below.

## ✨ Key Features

### 🧠 Personal Knowledge Management
- **Save & Organize**: Capture web pages, notes, and ideas with automatic tagging
- **Semantic Search**: Find anything using natural language queries
- **Memory Chat**: Have conversations with your saved knowledge using RAG
- **Rich Text Editor**: TipTap-powered note editor with formatting toolbar
- **Memory Context**: Attach memories directly to chat for focused conversations

### 🤖 AI Agent Studio
- **Pre-built Agents**: 6 ready-to-use agents (Research Assistant, Code Helper, Creative Writer, Study Buddy, Summarizer, Devil's Advocate)
- **Custom Agents**: Create your own agents with custom system prompts
- **Agent Selection**: Switch between agents in both the app and browser extension

### 🌐 Browser Extension
- **Quick Capture**: Save pages with one click from Chrome, Edge, or Firefox
- **Sidebar Chat**: Chat with AI directly in your browser
- **Agent Switching**: Select different AI personalities for different tasks
- **Resizable Sidepanel**: Drag to resize the sidebar width (300-600px)
- **Page Content Push**: Sidebar pushes page content aside instead of overlaying

### 🔒 Privacy-First
- **Local-First**: All data stored on your machine by default
- **Encrypted Database**: SQLCipher encryption at rest
- **No Telemetry**: Your data never leaves your device

### 🔌 Provider Agnostic
- **Ollama**: Run models locally (Llama, Mistral, Qwen, etc.)
- **OpenAI**: GPT-4o, GPT-4, GPT-3.5
- **OpenRouter**: Access 100+ models
- **Morpheus**: Decentralized AI
- **Venice**: Privacy-focused AI

### 🔐 Security Features
- **Lock App**: Quickly lock the app and require password to re-enter
- **Auto-expanding Input**: Chat input grows with your message
- **Smart Model Filtering**: Embedding models filtered from chat dropdown

---

## 🚀 Quick Start

### Prerequisites

- **Node.js** 18+ and **pnpm**
- **Python** 3.12 (not 3.13)
- **Poetry** for Python dependency management

### Installation

#### macOS

```bash
# Install dependencies
pnpm install

# Install backend
cd backend && poetry install && cd ..

# Build native messaging stub (compiles C with clang)
pnpm build:stub

# Start development
pnpm app
```

#### Linux

```bash
# Install dependencies
pnpm install

# Install backend
cd backend && poetry install && cd ..

# Build native messaging stub (compiles C with gcc)
pnpm build:stub

# Start development
pnpm app
```

#### Windows

```powershell
# Run the automated setup script
.\scripts\setup-windows.ps1

# Or manually:
pnpm install
cd backend
poetry env use python3.12
poetry install
cd ..
pnpm ext
pnpm build:stub
```

### Running the App

```bash
# Start backend + Electron app
pnpm app

# Start backend only
pnpm backend

# Build extension
pnpm ext
```

---

## 📦 Building for Distribution

### All Platforms

```bash
# Build everything (backend + stub + app)
pnpm build:all
```

### Platform-Specific

| Platform | Command | Output |
|----------|---------|--------|
| **Windows** | `pnpm build:app` | `.exe` installer (NSIS) |
| **macOS** | `pnpm build:app` | `.dmg` disk image |
| **Linux** | `pnpm build:app` | `.AppImage` + `.deb` |

### Release Builds (with code signing)

```bash
# macOS (requires Apple Developer credentials)
NOTARIZE=1 pnpm build:all:release

# Set these in .env.local:
# APPLE_ID=your@email.com
# APPLE_APP_SPECIFIC_PASSWORD=xxxx-xxxx-xxxx-xxxx
# APPLE_TEAM_ID=XXXXXXXXXX
# CODESIGN_IDENTITY="Developer ID Application: Your Name"
```

---

## 🏗️ Project Structure

```
thinkos/
├── app/              # Electron + React desktop app
│   ├── electron/     # Main process (native messaging, backend lifecycle)
│   ├── src/          # React frontend
│   └── build/        # Icons and entitlements
├── backend/          # Python FastAPI server
│   ├── app/          # Application code
│   │   ├── db/       # Database models and migrations
│   │   ├── routes/   # API endpoints
│   │   └── services/ # Business logic (AI, embeddings, etc.)
│   └── native_host/  # Native messaging stub (C/Python)
├── extension/        # Browser extension (Chrome/Firefox/Edge)
│   ├── src/          # React components
│   └── dist/         # Built extension
└── .ai/docs/         # Feature documentation
```

---

## 🤖 Pre-built Agents

ThinkOS comes with 6 pre-built AI agents:

| Agent | Description |
|-------|-------------|
| **Research Assistant** | Deep research and analysis specialist |
| **Code Helper** | Expert programming assistant for debugging and code review |
| **Creative Writer** | Imaginative writing partner for stories and content |
| **Study Buddy** | Patient tutor that explains concepts clearly |
| **Summarizer** | Concise summarization expert |
| **Devil's Advocate** | Critical thinker that challenges assumptions |

Create custom agents in the **Agents** page (Bot icon in sidebar).

---

## 🔧 Configuration

### Data Locations

| Platform | Location |
|----------|----------|
| **Windows** | `%LOCALAPPDATA%\Think\` |
| **macOS** | `~/Library/Application Support/Think/` |
| **Linux** | `~/.local/share/Think/` |

### Native Messaging Socket

| Platform | Location |
|----------|----------|
| **Windows** | `\\.\pipe\think-native` |
| **macOS/Linux** | `~/.think/native.sock` |

---

## 📚 Documentation

- [Browser Extension Setup](.ai/docs/extension.md)
- [Building for Distribution](.ai/docs/distribution.md)
- [Feature Overhaul Guide](.ai/docs/FEATURE_OVERHAUL_GUIDE.md)
- [Implementation Guide](.ai/docs/IMPLEMENTATION_GUIDE.md)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18 + TypeScript + Tailwind CSS + shadcn/ui |
| **Desktop** | Electron 33 |
| **Backend** | Python 3.12 + FastAPI + SQLAlchemy |
| **Database** | SQLite + SQLCipher (encrypted) |
| **Vectors** | sqlite-vec for embeddings |
| **Extension** | Chrome Manifest V3 + React |
| **Native Messaging** | C (macOS/Linux) / Python (Windows) |

---

## 🔀 Fork Enhancements

This fork extends the base ThinkOS with additional capabilities:

### 🤖 Browser Automation
- **Playwright Integration**: Automated browser control for web tasks
- **ThinkOSBrowserAgent**: AI-powered browser automation agent
- **Live Browser View**: Real-time browser preview in the app
- **vLLM Support**: Local browser-use model hosting

### 🎙️ Voice & Multi-modal
- **Text-to-Speech**: Local Chatterbox TTS + Replicate cloud fallback
- **Speech-to-Text**: Local Canary-Qwen STT + Replicate cloud fallback
- **Vision Processing**: Image analysis via OpenRouter Qwen3-VL

### 🛠️ Enhanced Agent Studio
- **Custom Tools**: Create and assign tools to agents
- **Workflow Builder**: Multi-step agent workflows with parallel execution
- **Agent Templates**: Pre-built agent configurations
- **WebSocket Streaming**: Real-time agent output streaming

### 📦 Infrastructure
- **Auto-updater**: Built-in update checking and installation
- **Cross-platform**: Full Windows, macOS, and Linux support
- **Inter Font**: Modern typography throughout the app

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

[Apache 2.0](LICENSE)

---
