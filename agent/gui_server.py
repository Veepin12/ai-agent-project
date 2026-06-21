import os
import json
import asyncio
import uuid
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.core import OmegaAgent
from agent.tools import list_dir, read_file, write_file, run_command

app = FastAPI(title="Omega Code Desktop Backend")

# Enable CORS for local dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

WORKSPACE_DIR = os.path.abspath(os.getcwd())

# In-memory session store for pending tool approvals
# ws_session_id -> { approval_id -> asyncio.Future }
pending_approvals: Dict[str, Dict[str, asyncio.Future]] = {}

class MCPConfig(BaseModel):
    name: str
    command: str
    args: List[str] = []

@app.get("/api/files")
def get_files(path: str = "."):
    """Get files for explorer."""
    return list_dir(path)

@app.get("/api/file")
def get_file_content(path: str):
    """Read file content."""
    res = read_file(path)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@app.post("/api/file")
def save_file_content(path: str, content: str):
    """Save file content."""
    res = write_file(path, content)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@app.get("/api/git/status")
def get_git_status():
    """Get git status details."""
    res = run_command("git status")
    return res

@app.get("/api/mcp")
def list_mcp_servers():
    """List configured MCP servers."""
    config_path = os.path.join(WORKSPACE_DIR, "mcp_servers.json")
    if not os.path.exists(config_path):
        return {}
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception:
        return {}

@app.post("/api/mcp")
def add_mcp_server(config: MCPConfig):
    """Add a new MCP server configuration."""
    config_path = os.path.join(WORKSPACE_DIR, "mcp_servers.json")
    servers = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                servers = json.load(f)
        except Exception:
            pass
            
    servers[config.name] = {
        "command": config.command,
        "args": config.args
    }
    
    try:
        with open(config_path, "w") as f:
            json.dump(servers, f, indent=2)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/mcp/{name}")
def delete_mcp_server(name: str):
    """Delete an MCP server configuration."""
    config_path = os.path.join(WORKSPACE_DIR, "mcp_servers.json")
    servers = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                servers = json.load(f)
        except Exception:
            pass
            
    if name in servers:
        del servers[name]
        try:
            with open(config_path, "w") as f:
                json.dump(servers, f, indent=2)
            return {"success": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=404, detail="Server not found")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    session_id = str(uuid.uuid4())
    pending_approvals[session_id] = {}
    
    # Initialize the agent for this WebSocket session
    agent = OmegaAgent()
    
    # Connect external MCP servers on startup
    await agent.connect_external_mcp_servers()
    
    # Send connection success and connected extensions
    await websocket.send_json({
        "type": "connection_established",
        "extensions": list(agent.mcp_clients.keys()),
        "mode": agent.mode,
        "model": agent.model,
        "workspace": WORKSPACE_DIR
    })
    
    # Define callbacks that push details directly over WebSocket
    def agent_callback(step_type: str, name: str, data: Any):
        # We wrap it in a thread-safe / async loop task
        asyncio.run_coroutine_threadsafe(
            websocket.send_json({
                "type": "callback",
                "step_type": step_type,
                "name": name,
                "data": data
            }),
            asyncio.get_event_loop()
        )
        
    async def gui_approval_callback(tool_name: str, tool_args: Dict[str, Any]) -> bool:
        approval_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        pending_approvals[session_id][approval_id] = future
        
        # Send the approval request to the React client
        await websocket.send_json({
            "type": "approval_request",
            "id": approval_id,
            "tool_name": tool_name,
            "tool_args": tool_args
        })
        
        # Await client response
        approved = await future
        return approved

    try:
        while True:
            # Receive user message from WebSocket
            data = await websocket.receive_text()
            message = json.loads(data)
            
            msg_type = message.get("type")
            
            if msg_type == "chat_prompt":
                prompt = message.get("prompt")
                # Run execute loop in a separate task so it doesn't block receiving WebSocket messages
                asyncio.create_task(
                    run_agent_loop(agent, prompt, agent_callback, gui_approval_callback, websocket)
                )
                
            elif msg_type == "approval_response":
                approval_id = message.get("id")
                approved = message.get("approved", False)
                future = pending_approvals[session_id].get(approval_id)
                if future and not future.done():
                    future.set_result(approved)
                    del pending_approvals[session_id][approval_id]
                    
            elif msg_type == "change_mode":
                new_mode = message.get("mode")
                if new_mode in ("ask", "plan", "code"):
                    agent.mode = new_mode
                    await websocket.send_json({
                        "type": "mode_changed",
                        "mode": agent.mode
                    })
                    
            elif msg_type == "change_model":
                new_model = message.get("model")
                if new_model:
                    agent.model = new_model
                    await websocket.send_json({
                        "type": "model_changed",
                        "model": agent.model
                    })
                    
            elif msg_type == "clear_history":
                agent.clear_history()
                await websocket.send_json({
                    "type": "history_cleared"
                })
                
    except WebSocketDisconnect:
        pass
    finally:
        # Cleanup
        await agent.disconnect_external_mcp_servers()
        if session_id in pending_approvals:
            del pending_approvals[session_id]

async def run_agent_loop(agent: OmegaAgent, prompt: str, callback, approval_callback, websocket: WebSocket):
    try:
        final_response = await agent.execute_loop(
            prompt,
            callback=callback,
            approval_callback=approval_callback
        )
        await websocket.send_json({
            "type": "chat_response",
            "response": final_response
        })
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })

# Serve static frontend files if compiled
frontend_dist = os.path.join(WORKSPACE_DIR, "gui", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
