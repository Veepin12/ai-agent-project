import os
import sys
import json
import asyncio
from typing import Any, Dict
from dotenv import load_dotenv, set_key

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style

from agent.core import OmegaAgent

load_dotenv()

# Initialize rich console
console = Console()

# Prompt toolkit custom styling
prompt_style = Style.from_dict({
    'prompt': '#00ffcc bold',
    'arrow': '#ff007f bold',
    'mode': '#ffcc00 bold',
})

def print_banner():
    """Display the startup banner."""
    console.print("\n")
    banner_text = (
        "[bold cyan]██████╗ ███╗   ███╗███████╗ ██████╗  █████╗      ██████╗ ██████╗ ██████╗ ███████╗\n"
        "██╔═══██╗████╗ ████║██╔════╝██╔════╝ ██╔══██╗    ██╔════╝██╔═══██╗██╔══██╗██╔════╝\n"
        "██║   ██║██╔████╔██║█████╗  ██║  ███╗███████║    ██║     ██║   ██║██║  ██║█████╗  \n"
        "██║   ██║██║╚██╔╝██║██╔══╝  ██║   ██║██╔══██║    ██║     ██║   ██║██║  ██║██╔══╝  \n"
        "╚██████╔╝██║ ╚═╝ ██║███████╗╚██████╔╝██║  ██║    ╚██████╗╚██████╔╝██████╔╝███████╗\n"
        " ╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝     ╚═════╝ ╚═════╝╚══════╝╚══════╝[/bold cyan]\n"
        "                                                                               \n"
        "           [bold green]Omega Code Agent (v1.1.0)[/bold green] | Powered by Groq/OpenAI/Gemini\n"
        "       [dim]Claude Code architecture with custom interactive modes and MCP extensions[/dim]\n"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))
    console.print("[dim]Slash Commands: [bold white]/ask[/bold white] | [bold white]/plan[/bold white] | [bold white]/code[/bold white] | [bold white]/mcp[/bold white] | [bold white]/help[/bold white] | [bold white]/exit[/bold white][/dim]\n")

def print_help():
    """Print the help guide."""
    table = Table(title="Interactive Commands", border_style="cyan")
    table.add_column("Command", style="bold yellow")
    table.add_column("Description", style="white")
    table.add_row("/ask", "Switch agent to ASK mode (safe question-answering, blocks mutations)")
    table.add_row("/plan", "Switch agent to PLAN mode (requires plans before executing)")
    table.add_row("/code or /agent", "Switch agent to CODE mode (autonomous file/command editing)")
    table.add_row("/mcp list", "List all configured external MCP servers and imported tools")
    table.add_row("/mcp add <name> <cmd> [args...]", "Configure and connect a new external MCP server")
    table.add_row("/mcp remove <name>", "Disconnect and remove an external MCP server")
    table.add_row("/clear", "Reset current agent chat context and clear memory")
    table.add_row("/help", "Show this help screen")
    table.add_row("/exit or /quit", "Exit the Omega Code CLI")
    
    console.print(table)

def handle_agent_callback(step_type: str, name: str, data: Any):
    """
    Handle and format callback notifications from the agent loop.
    """
    if step_type == "thinking":
        console.print("[dim italic cyan]Thinking...[/dim italic cyan]")
    elif step_type == "tool_call":
        args_formatted = json.dumps(data, indent=2)
        panel_content = Syntax(args_formatted, "json", theme="monokai", word_wrap=True)
        console.print(Panel(
            panel_content, 
            title=f"🔧 [bold yellow]Tool Call: {name}[/bold yellow]", 
            border_style="yellow", 
            expand=False
        ))
    elif step_type == "tool_response":
        try:
            parsed = json.loads(data)
            if "error" in parsed:
                console.print(f"❌ [bold red]Tool Execution Error:[/bold red] {parsed['error']}\n")
            elif "success" in parsed and parsed["success"]:
                console.print(f"✅ [bold green]Tool Execution Success:[/bold green] {parsed.get('message', 'Completed')}\n")
            elif "exit_code" in parsed:
                code = parsed["exit_code"]
                color = "green" if code == 0 else "red"
                console.print(f"📟 [bold {color}]Terminal Exit Code {code}[/bold {color}]\n")
                if parsed.get("stdout"):
                    console.print(Panel(parsed["stdout"][:1000] + ("\n... [truncated]" if len(parsed["stdout"]) > 1000 else ""), title="Stdout", border_style="dim"))
                if parsed.get("stderr"):
                    console.print(Panel(parsed["stderr"][:1000] + ("\n... [truncated]" if len(parsed["stderr"]) > 1000 else ""), title="Stderr", border_style="red"))
            elif "content" in parsed:
                lines_cnt = len(parsed.get("content", "").splitlines())
                console.print(f"📖 [bold green]Read File Success:[/bold green] Loaded {lines_cnt} lines (lines {parsed.get('start_line')}-{parsed.get('end_line')})\n")
            elif "items" in parsed:
                console.print(f"📁 [bold green]List Directory Success:[/bold green] Found {len(parsed['items'])} items in {parsed['path']}\n")
            elif "matches" in parsed:
                console.print(f"🔍 [bold green]Search Grep Success:[/bold green] Found {len(parsed['matches'])} matches\n")
            elif "files" in parsed:
                console.print(f"📂 [bold green]Find Files Success:[/bold green] Located {len(parsed['files'])} files\n")
            else:
                console.print("✅ [bold green]Tool Executed Successfully[/bold green]\n")
        except Exception:
            # Fallback for plain text tool outputs (e.g. from external MCP servers)
            console.print(Panel(data[:2000] + ("\n... [truncated]" if len(data) > 2000 else ""), title="External Tool Output", border_style="green"))
            console.print("\n")
    elif step_type == "error":
        console.print(Panel(f"[bold red]{data}[/bold red]", title="Error Details", border_style="red"))

async def ask_tool_approval(tool_name: str, tool_args: Dict[str, Any]) -> bool:
    """Prompt the user in the CLI to approve or reject a tool execution (VS Code style)."""
    console.print("\n[bold yellow]🛡️  Tool Execution Request[/bold yellow]")
    console.print(f"Tool: [bold cyan]{tool_name}[/bold cyan]")
    args_json = json.dumps(tool_args, indent=2)
    console.print(Panel(Syntax(args_json, "json", theme="monokai"), title="Parameters", border_style="dim"))
    
    # Prompt user for confirmation
    try:
        user_choice = input("Accept execution of this tool? [y/N]: ").strip().lower()
        if user_choice in ("y", "yes"):
            console.print("[green]✓ Executing...[/green]\n")
            return True
        else:
            console.print("[red]✗ Execution Rejected by User[/red]\n")
            return False
    except (KeyboardInterrupt, EOFError):
        console.print("[red]✗ Execution Cancelled[/red]\n")
        return False

def ensure_api_key():
    """Ensure that GROQ_API_KEY, OPENAI_API_KEY, or GEMINI_API_KEY is present."""
    if not os.environ.get("GROQ_API_KEY") and not os.environ.get("OPENAI_API_KEY") and not os.environ.get("GEMINI_API_KEY"):
        console.print("[bold yellow]⚠️  No API Key found in environment.[/bold yellow]")
        console.print("Please enter your [bold cyan]Gemini API Key[/bold cyan], [bold cyan]Groq API Key[/bold cyan], or [bold cyan]OpenAI API Key[/bold cyan].")
        api_key = input("API Key: ").strip()
        if not api_key:
            console.print("[bold red]An API key is required to run the agent. Exiting.[/bold red]")
            sys.exit(1)
        # Write to .env file
        env_path = os.path.join(os.getcwd(), ".env")
        if api_key.startswith("AIzaSy"):
            key_name = "GEMINI_API_KEY"
        elif api_key.startswith("gsk_"):
            key_name = "GROQ_API_KEY"
        else:
            key_name = "OPENAI_API_KEY"
        try:
            set_key(env_path, key_name, api_key)
            os.environ[key_name] = api_key
            console.print(f"[green]API Key saved as {key_name} to .env file.[/green]\n")
        except Exception as e:
            os.environ[key_name] = api_key
            console.print(f"[yellow]Could not write key to .env file, but it has been set in memory: {str(e)}[/yellow]\n")

async def handle_mcp_commands(user_input: str, agent: OmegaAgent):
    """Handle /mcp subcommands."""
    parts = user_input.split()
    if len(parts) == 1:
        console.print("[bold red]Invalid MCP command. Use /mcp list, /mcp add, or /mcp remove.[/bold red]")
        return
        
    subcommand = parts[1].lower()
    config_path = os.path.join(os.getcwd(), "mcp_servers.json")
    
    # Load configuration
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception:
            pass
            
    if subcommand == "list":
        table = Table(title="Connected MCP Extensions", border_style="cyan")
        table.add_column("Extension Name", style="bold green")
        table.add_column("Launch Command", style="yellow")
        table.add_column("Imported Tools Count", style="cyan")
        
        # Count tools per server
        tools_counts = {}
        for pref_tool, (srv, _) in agent.external_tools.items():
            tools_counts[srv] = tools_counts.get(srv, 0) + 1
            
        for srv_name, srv_cfg in config.items():
            cmd_str = f"{srv_cfg.get('command')} {' '.join(srv_cfg.get('args', []))}"
            count = tools_counts.get(srv_name, 0)
            table.add_row(srv_name, cmd_str, str(count))
            
        console.print(table)
        
    elif subcommand == "add":
        if len(parts) < 4:
            console.print("[bold red]Usage: /mcp add <name> <command> [args...][/bold red]")
            return
        name = parts[2]
        cmd = parts[3]
        args = parts[4:]
        
        config[name] = {"command": cmd, "args": args}
        try:
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            console.print(f"[green]✓ MCP extension config '{name}' saved to mcp_servers.json.[/green]")
            console.print("[dim]Connecting and importing tools...[/dim]")
            await agent.connect_external_mcp_servers()
            console.print(f"[green]✓ Successfully reconnected. Connected MCPs: {list(agent.mcp_clients.keys())}[/green]")
        except Exception as e:
            console.print(f"[bold red]Error updating MCP config: {e}[/bold red]")
            
    elif subcommand == "remove":
        if len(parts) < 3:
            console.print("[bold red]Usage: /mcp remove <name>[/bold red]")
            return
        name = parts[2]
        if name in config:
            del config[name]
            try:
                with open(config_path, "w") as f:
                    json.dump(config, f, indent=2)
                console.print(f"[green]✓ MCP extension '{name}' removed from configuration.[/green]")
                console.print("[dim]Reconnecting servers...[/dim]")
                await agent.connect_external_mcp_servers()
                console.print("[green]✓ Reconnection complete.[/green]")
            except Exception as e:
                console.print(f"[bold red]Error removing MCP extension: {e}[/bold red]")
        else:
            console.print(f"[bold red]Extension '{name}' not found in configuration.[/bold red]")

async def main():
    ensure_api_key()
    print_banner()
    
    agent = OmegaAgent()
    console.print("[dim]Connecting to external MCP servers...[/dim]")
    await agent.connect_external_mcp_servers()
    if agent.mcp_clients:
        console.print(f"[green]✓ Connected to extensions: {list(agent.mcp_clients.keys())}[/green]\n")
    else:
        console.print("[dim]No external MCP extensions connected. (Use /mcp add to configure)[/dim]\n")
        
    session = PromptSession()
    
    while True:
        try:
            # Dynamically update prompt mode suffix
            prompt_msg = [
                ('class:prompt', 'omega-code '),
                ('class:mode', f'({agent.mode}) '),
                ('class:arrow', '❯ '),
            ]
            
            user_input = await session.prompt_async(prompt_msg, style=prompt_style)
            user_input = user_input.strip()
            
            if not user_input:
                continue
                
            # Handle standard CLI commands
            if user_input.lower() in ('/exit', '/quit'):
                console.print("[cyan]Exiting Omega Code. Goodbye![/cyan]")
                break
            elif user_input.lower() == '/clear':
                agent.clear_history()
                console.print("[green]Conversation history cleared.[/green]\n")
                continue
            elif user_input.lower() == '/help':
                print_help()
                continue
                
            # Mode toggle commands
            elif user_input.lower() == '/ask':
                agent.mode = "ask"
                console.print("[yellow]✓ Switched to ASK mode (Safe Q&A, no code changes allowed).[/yellow]\n")
                continue
            elif user_input.lower() == '/plan':
                agent.mode = "plan"
                console.print("[yellow]✓ Switched to PLAN mode (Agent will draft plans before modifying code).[/yellow]\n")
                continue
            elif user_input.lower() in ('/code', '/agent'):
                agent.mode = "code"
                console.print("[yellow]✓ Switched to CODE mode (Full execution permissions).[/yellow]\n")
                continue
            elif user_input.startswith('/mode'):
                parts = user_input.split()
                if len(parts) > 1 and parts[1].lower() in ('ask', 'plan', 'code'):
                    agent.mode = parts[1].lower()
                    console.print(f"[yellow]✓ Switched to {agent.mode.upper()} mode.[/yellow]\n")
                else:
                    console.print("[bold red]Usage: /mode <ask|plan|code>[/bold red]\n")
                continue
                
            # Handle MCP manager command
            elif user_input.startswith('/mcp'):
                await handle_mcp_commands(user_input, agent)
                continue
            
            # Run the agent reasoning loop asynchronously
            console.print("\n[bold blue]=== Starting Agent Loop ===[/bold blue]")
            final_response = await agent.execute_loop(
                user_input, 
                callback=handle_agent_callback, 
                approval_callback=ask_tool_approval
            )
            
            console.print("[bold blue]=== Final Agent Response ===[/bold blue]")
            console.print(Markdown(final_response))
            console.print("\n")
            
        except KeyboardInterrupt:
            console.print("\n[yellow]KeyboardInterrupt. Type /exit to quit.[/yellow]\n")
        except EOFError:
            console.print("\n[cyan]Exiting Omega Code. Goodbye![/cyan]")
            break
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {str(e)}[/bold red]\n")
            
    # Cleanup MCP connections on exit
    console.print("[dim]Closing MCP connections...[/dim]")
    await agent.disconnect_external_mcp_servers()

if __name__ == "__main__":
    asyncio.run(main())
