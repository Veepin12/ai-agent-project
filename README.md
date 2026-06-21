# Omega Code: Claude-Style Developer Agent & Console

Omega Code is a production-grade, autonomous developer agent and interactive desktop console designed to replicate the elite developer experience of **Claude Code**. Equipped with real-time reasoning loops, interactive tool approvals, multi-chat recents memory, and speech recognition/synthesis, it acts as a powerful companion directly integrated with your workspace.

---

## 🌟 Key Features

1. **Dual Console Interfaces:**
   - **CLI Mode:** Command-line developer terminal with live reasoning indicators, slash commands, and status prompts.
   - **Desktop GUI Console:** A premium dark-themed web console styled exactly like the Claude web interface.
2. **Interactive Agentic Modes:**
   - `ask`: Safe mode for answering questions without mutating workspace files or executing commands.
   - `plan`: Design mode that forces the agent to outline step-by-step implementation plans for approval before making changes.
   - `code`: Autonomous developer mode with full execution/mutation permissions.
3. **Dangerous Tool Approvals:** Requires user confirmation (`[y/N]` prompt in CLI, visual pulsing overlay cards in GUI) before running mutating or shell execution tools (`run_command`, `write_file`, `patch_file`).
4. **Voice Integration:**
   - **Speech-to-Text (STT):** Click the microphone button in the input card to dictate queries using your browser's Speech Recognition API.
   - **Text-to-Speech (TTS):** Toggle audio response mode using the volume icon to have assistant messages spoken aloud automatically.
5. **MCP client support:** Connects dynamically to external stdio-based Model Context Protocol servers to imports their tools (configured via `mcp_servers.json`).
6. **Code & Diff renderers:** Monospace code syntax cards and color-coded unified diff blocks (highlighting `+` green additions and `-` red deletions) to present agent modifications clearly.

---

## 🚀 Step-by-Step Setup Guide

### 1. Prerequisites
- **Python 3.12+**
- **Node.js 18+ & npm** (required to compile and bundle the React GUI files)
- **Groq API Key** (for fast, efficient model completions) or **OpenAI API Key**

### 2. Installation
Clone the repository and navigate into the root directory:
```bash
git clone https://github.com/Veepin12/ai-agent-project.git
cd ai-agent-project
```

### 3. Setup Virtual Environment & Python dependencies
Create a python virtual environment and install backend requirements:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template configuration file to `.env`:
```bash
cp .env.example .env
```
Open the `.env` file and insert your API Key:
```env
# Groq API Configuration
GROQ_API_KEY="your_groq_api_key"
GROQ_BASE_URL=https://api.groq.com/openai/v1
GROQ_MODEL=llama-3.3-70b-versatile

# Fallback OpenAI API Configuration
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o
```

### 5. Build the React GUI Frontend
Navigate into the React directory, install packages, and compile the static bundle:
```bash
cd gui/frontend
npm install
npm run build
cd ../..
```
This builds and compiles the assets (`dist/index.html` and bundled JS/CSS assets) which are served by FastAPI.

---

## 🛠️ Running the Application

Omega Code functions in three distinct runner modes depending on your workflow:

### Mode A: Interactive Desktop GUI Console
Lunches the FastAPI backend and automatically opens the browser window displaying the Claude-style console:
```bash
.venv/bin/python omega_gui.py
```
*Port default:* `http://localhost:8000`

### Mode B: Command-Line Interface (CLI)
Starts the interactive CLI loop directly inside your active terminal session:
```bash
.venv/bin/python omega.py
```
- Toggle modes in terminal using `/ask`, `/plan`, or `/code`.
- Clear context using `/clear`.

### Mode C: Stdio MCP Server
Exposes the agent's internal development tools over stdio to Cursor, VS Code, or Claude Desktop:
```bash
.venv/bin/python omega.py --mcp
```

---

## 🤝 Contribution & Pull Request (PR) Guide

We welcome contributions from the developer community! If you want to contribute, please follow this step-by-step contribution flow:

### 1. Fork and Clone
Fork the repository on GitHub, then clone your fork locally:
```bash
git clone https://github.com/YOUR_USERNAME/ai-agent-project.git
cd ai-agent-project
```

### 2. Create a Feature Branch
Always create a clean, descriptive branch for your changes:
```bash
git checkout -b feature/your-awesome-feature
```

### 3. Coding Guidelines
- **Modular Backend:** Keep agent logic compartmentalized within the `agent/` subfolders (`core.py`, `gui_server.py`, `tools.py`).
- **Clean Styles:** Do not load large CSS framework dependencies. Build styling updates using pure Vanilla CSS variables and selectors in [index.css](file:///Users/veepinchaudhary8115/Documents/GitHub/ai-agent-project/gui/frontend/src/index.css).
- **Tool Safety:** Ensure new tools handle exceptions gracefully and return structured JSON schemas.

### 4. Build & Test Verification
Before proposing a Pull Request, verify that all files compile and compile/build successfully:
- **Validate Python Syntax:**
  ```bash
  .venv/bin/python -m py_compile agent/core.py agent/gui_server.py omega.py omega_gui.py
  ```
- **Validate React Build:**
  ```bash
  cd gui/frontend && npm run build && cd ../..
  ```

### 5. Commit and Push
Write semantic, descriptive commit messages:
```bash
git add .
git commit -m "feat: add support for voice pitch adjustments inside settings"
git push origin feature/your-awesome-feature
```

### 6. Create a Pull Request (PR)
1. Go to the original [ai-agent-project repository](https://github.com/Veepin12/ai-agent-project) on GitHub.
2. Click **New Pull Request** and choose your branch.
3. Fill out the PR template by describing:
   - What feature/bugfix you are introducing.
   - Visual screenshots or terminal records demonstrating the change.
   - Verification steps you performed (e.g. build logs, compile tests).
