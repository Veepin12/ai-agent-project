import os
import json
from typing import List, Dict, Any, Generator, Callable, Optional, Awaitable
from openai import AsyncOpenAI
from dotenv import load_dotenv

from agent.tools import TOOLS_SCHEMA, TOOLS_MAPPING

# Load env variables
load_dotenv()

# Base workspace directory
WORKSPACE_DIR = os.path.abspath(os.getcwd())

SYSTEM_PROMPT = """
You are Omega Code (version 1.0.0), a high-performance developer agent modeled after the best characteristics of Claude Code. You have direct read/write access to the local filesystem and terminal execution tools.

Your design and behavior adhere to the following principles:

1. CORE PERSONA (Claude-Style Behavior):
   - Be clear, helpful, direct, and professional. Avoid boilerplate pleasantries (do NOT say "Sure, I can help with that!" or "Here is the solution!"). Get straight to the task and explain your steps with technical depth.
   - Be opinionated on code quality: suggest best practices, proper error handling, robust type hinting, and testing.

2. OUTPUT FORMATTING:
   - Always structure your responses by separating code blocks and prose clearly.
   - Every single code block must begin with an explicit language identifier (e.g., `cpp`, `python`, `javascript`, `html`, `css`, `bash`, `json`, `yaml`, `diff`, etc.) immediately after the triple backticks.
   - All code outputs must be presented in standard GitHub-Flavored Markdown fenced code blocks to ensure they display with a "Copy" button in markdown readers. Keep code clean and ready to copy-paste.

3. UNDERSTAND AND PLAN:
   - Carefully analyze the user request and explore the workspace before writing code.
   - List files, find relevant files, and search with `search_grep` to fully understand the project architecture.
   - Outline a clear, step-by-step implementation plan. Keep it structured and maintain a mental "progress list".

4. CAREFUL FILESYSTEM MUTATIONS:
   - Prefer `patch_file` (specific edits) over overwriting the entire file with `write_file`, especially for large files.
   - Double check your replacements before calling `patch_file`. Ensure search blocks match the target file exactly, including leading spaces/tabs and newlines.
   - Never write placeholders like `// TODO: implement later` unless requested. Always write the full implementation.

5. CODE OUTPUTS AND DIFFS:
   - When presenting code edits, suggestions, or changes to existing files, always format them as a standard unified diff within a ```diff block.
   - Show precisely what to delete (prefix lines with `-`) and what to add (prefix lines with `+`), so the user can easily review the changes.

6. TEST AND VERIFY:
   - Use `run_command` to execute tests, compilers, or linters to verify your changes. If a change breaks the project, debug and fix it immediately. Do not leave the workspace in a broken state.

7. GIT INTEGRITY:
   - Be git-aware. Recognize if you are in a git repository.
   - When completing a task, summarize the changes and optionally offer a git commit command or describe the changes for their git stage.

TOOL USAGE RULES:
- You must call tools sequentially or concurrently as needed.
- If a tool fails, read the error message carefully and self-correct.
- You must answer using standard markdown formatting.

Always keep your reasoning explicit but concise. Focus on shipping working code.
"""

class OmegaAgent:
    def __init__(self, model: str = None, api_key: str = None, base_url: str = None):
        """
        Initialize the Omega Code agent, supporting Groq, OpenAI, and Gemini backends.
        """
        groq_key = os.environ.get("GROQ_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY")
        
        # Decide the default model based on key availability
        default_model = "llama-3.3-70b-versatile"
        if groq_key:
            default_model = "llama-3.3-70b-versatile"
        elif openai_key:
            default_model = "gpt-4o"
        elif gemini_key:
            default_model = "gemini-2.5-flash"
            
        self.model = model or os.environ.get("GROQ_MODEL") or os.environ.get("OPENAI_MODEL") or os.environ.get("GEMINI_MODEL") or default_model
        
        # Resolve api_key and base_url
        if self.model.startswith("gemini-"):
            self.api_key = api_key or gemini_key
            self.base_url = base_url or os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
        elif self.model.startswith(("gpt-", "o1-", "o3-", "text-")):
            self.api_key = api_key or openai_key
            self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        else:
            # Assume Groq or general fallback
            self.api_key = api_key or groq_key or openai_key or gemini_key
            if not groq_key and not openai_key and gemini_key:
                self.base_url = base_url or os.environ.get("GEMINI_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai/"
            else:
                self.base_url = base_url or os.environ.get("GROQ_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
        
        # Initialize the OpenAI client (which is compatible with OpenAI, Groq, and Gemini APIs)
        client_kwargs = {}
        if self.api_key:
            client_kwargs["api_key"] = self.api_key
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
            
        self.client = AsyncOpenAI(**client_kwargs)
        self.history: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Mode management (code, ask, plan)
        self.mode = "code"
        
        # MCP external clients registry
        self.mcp_clients: Dict[str, Any] = {}
        self.external_tools: Dict[str, tuple] = {}  # prefixed_tool_name -> (server_name, original_tool_name)
        self.dynamic_tools_schema: List[Dict[str, Any]] = []

    async def connect_external_mcp_servers(self):
        """Read mcp_servers.json, connect to each server, and load their tools."""
        from contextlib import AsyncExitStack
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        
        self.exit_stack = AsyncExitStack()
        config_path = os.path.join(WORKSPACE_DIR, "mcp_servers.json")
        if not os.path.exists(config_path):
            return
            
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            return
            
        # Reset dynamic configurations
        self.mcp_clients = {}
        self.external_tools = {}
        self.dynamic_tools_schema = []
        
        for name, server_cfg in config.items():
            command = server_cfg.get("command")
            args = server_cfg.get("args", [])
            env = server_cfg.get("env")
            
            # Use current process environment as base if none is specified
            run_env = os.environ.copy()
            if env:
                run_env.update(env)
                
            if not command:
                continue
                
            try:
                params = StdioServerParameters(command=command, args=args, env=run_env)
                read_stream, write_stream = await self.exit_stack.enter_async_context(stdio_client(params))
                session = await self.exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
                
                await session.initialize()
                self.mcp_clients[name] = session
                
                tools_res = await session.list_tools()
                for tool in tools_res.tools:
                    prefixed_name = f"{name}_{tool.name}"
                    self.external_tools[prefixed_name] = (name, tool.name)
                    
                    openai_tool = {
                        "type": "function",
                        "function": {
                            "name": prefixed_name,
                            "description": tool.description or f"Tool from external MCP server '{name}'",
                            "parameters": tool.inputSchema
                        }
                    }
                    self.dynamic_tools_schema.append(openai_tool)
            except Exception as e:
                print(f"Error connecting to MCP server '{name}': {e}")

    async def disconnect_external_mcp_servers(self):
        """Close all external MCP server connections."""
        if hasattr(self, 'exit_stack'):
            await self.exit_stack.aclose()
        self.mcp_clients = {}
        self.external_tools = {}
        self.dynamic_tools_schema = []

    def get_messages_with_mode(self) -> List[Dict[str, Any]]:
        """Return conversation history with mode-specific instructions appended."""
        mode_instructions = ""
        if self.mode == "ask":
            mode_instructions = (
                "\n\nCRITICAL: You are currently in ASK mode. You are restricted to answering questions using your knowledge. "
                "You MUST NOT execute any commands, modify files, or use file mutation/execution tools (like run_command, write_file, patch_file). "
                "If the user request requires making code edits, explain what needs to be done in detail instead of executing it."
            )
        elif self.mode == "plan":
            mode_instructions = (
                "\n\nCRITICAL: You are currently in PLAN mode. For any request involving changes to code or executing commands, "
                "you must first outline a detailed step-by-step implementation plan (including files to create/modify and verification steps). "
                "Do not execute any tools yet. Present the plan and ask the user for approval first."
            )
        elif self.mode == "code":
            mode_instructions = (
                "\n\nYou are currently in CODE mode. You have full permission to propose code changes and run commands. "
                "You should execute tasks autonomously."
            )
            
        messages = []
        for msg in self.history:
            # Handle chat completion message object from history if it is not a dictionary
            if hasattr(msg, "role"):
                # Convert OpenAI message object to dict
                msg_dict = {"role": msg.role, "content": msg.content or ""}
                if msg.tool_calls:
                    # Convert tool calls to serializable form
                    msg_dict["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        } for tc in msg.tool_calls
                    ]
                msg = msg_dict

            if msg["role"] == "system":
                messages.append({"role": "system", "content": msg["content"] + mode_instructions})
            else:
                messages.append(msg)
        return messages

    def add_message(self, role: str, content: str):
        """Append a message to the conversation history."""
        self.history.append({"role": role, "content": content})

    def clear_history(self):
        """Reset the conversation history, keeping only the system prompt."""
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    async def execute_loop(
        self, 
        user_prompt: str, 
        callback: Optional[Callable[[str, str, Any], None]] = None,
        approval_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[bool]]] = None
    ) -> str:
        """
        Run the agentic tool-use loop for a given user prompt.
        """
        self.add_message("user", user_prompt)
        
        while True:
            if callback:
                callback("thinking", "model", None)
                
            messages_with_mode = self.get_messages_with_mode()
            
            # Combine static local tools and dynamic external tools
            combined_tools = TOOLS_SCHEMA + self.dynamic_tools_schema
            
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages_with_mode,
                    tools=combined_tools if combined_tools else None,
                    tool_choice="auto" if combined_tools else None,
                    stream=True
                )
                
                full_content = ""
                assembled_tool_calls = {}
                
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    
                    # Stream content chunk
                    if delta.content:
                        full_content += delta.content
                        if callback:
                            callback("content_chunk", "model", delta.content)
                            
                    # Assemble tool calls
                    if delta.tool_calls:
                        for tool_call in delta.tool_calls:
                            idx = tool_call.index
                            if idx not in assembled_tool_calls:
                                assembled_tool_calls[idx] = {
                                    "id": tool_call.id or "",
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""}
                                }
                            if tool_call.id:
                                assembled_tool_calls[idx]["id"] = tool_call.id
                            if tool_call.function:
                                if tool_call.function.name:
                                    assembled_tool_calls[idx]["function"]["name"] += tool_call.function.name
                                if tool_call.function.arguments:
                                    assembled_tool_calls[idx]["function"]["arguments"] += tool_call.function.arguments
                                    
            except Exception as e:
                err_msg = f"API Error: {str(e)}"
                if "api_key" in str(e).lower() or "apikey" in str(e).lower() or "unauthorized" in str(e).lower():
                    err_msg = "Error: API Key is missing or invalid. Please check your .env file or environment variables."
                if callback:
                    callback("error", "api", err_msg)
                return err_msg

            from types import SimpleNamespace
            
            tool_calls = []
            if assembled_tool_calls:
                for idx in sorted(assembled_tool_calls.keys()):
                    tc = assembled_tool_calls[idx]
                    tool_calls.append(SimpleNamespace(
                        id=tc["id"],
                        type=tc["type"],
                        function=SimpleNamespace(
                            name=tc["function"]["name"],
                            arguments=tc["function"]["arguments"]
                        )
                    ))
                    
            message = SimpleNamespace(
                role="assistant",
                content=full_content or None,
                tool_calls=tool_calls if tool_calls else None
            )
            
            self.history.append(message)

            if not tool_calls:
                final_content = message.content or ""
                if callback:
                    callback("done", "final_response", final_content)
                return final_content

            for tool_call in tool_calls:
                # Handle OpenAI SDK types
                tool_name = tool_call.function.name
                tool_args_str = tool_call.function.arguments
                tool_id = tool_call.id
                
                try:
                    tool_args = json.loads(tool_args_str)
                except Exception:
                    tool_args = {"raw_arguments": tool_args_str}
                    
                if callback:
                    callback("tool_call", tool_name, tool_args)
                    
                # Guard against mutating tools in ASK mode
                is_mutating_tool = tool_name in ("run_command", "write_file", "patch_file")
                if self.mode == "ask" and is_mutating_tool:
                    result_str = json.dumps({
                        "error": f"Rejection: Tool '{tool_name}' cannot be executed because the agent is currently in ASK mode."
                    }, indent=2)
                    if callback:
                        callback("tool_response", tool_name, result_str)
                    self.history.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": tool_name,
                        "content": result_str
                    })
                    continue
                
                # Check for approval on mutating tools
                if is_mutating_tool and approval_callback:
                    approved = await approval_callback(tool_name, tool_args)
                    if not approved:
                        result_str = json.dumps({
                            "error": f"Rejection: User rejected the execution of tool '{tool_name}'."
                        }, indent=2)
                        if callback:
                            callback("tool_response", tool_name, result_str)
                        self.history.append({
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": result_str
                        })
                        continue

                # Execute local tools
                if tool_name in TOOLS_MAPPING:
                    tool_func = TOOLS_MAPPING[tool_name]
                    try:
                        result = tool_func(**tool_args)
                        result_str = json.dumps(result, indent=2)
                    except Exception as e:
                        result_str = json.dumps({"error": f"Exception during execution: {str(e)}"}, indent=2)
                
                # Execute external MCP tools
                elif tool_name in self.external_tools:
                    server_name, original_tool = self.external_tools[tool_name]
                    session = self.mcp_clients.get(server_name)
                    if session:
                        try:
                            res = await session.call_tool(original_tool, arguments=tool_args)
                            # Convert response to content string
                            content_parts = []
                            for content in res.content:
                                if hasattr(content, 'text'):
                                    content_parts.append(content.text)
                                else:
                                    content_parts.append(str(content))
                            result_str = "\n".join(content_parts)
                        except Exception as e:
                            result_str = json.dumps({"error": f"Error calling external MCP tool: {str(e)}"}, indent=2)
                    else:
                        result_str = json.dumps({"error": f"External MCP server session '{server_name}' not found."}, indent=2)
                else:
                    result_str = json.dumps({"error": f"Tool '{tool_name}' not implemented."}, indent=2)
                    
                if callback:
                    callback("tool_response", tool_name, result_str)
                    
                self.history.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": result_str
                })
