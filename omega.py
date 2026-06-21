#!/usr/bin/env python3
import sys
import argparse

def main():
    parser = argparse.ArgumentParser(description="Omega Code Agent: A high-performance coding agent and MCP server.")
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Run as an MCP (Model Context Protocol) server instead of the interactive CLI."
    )
    args = parser.parse_args()

    try:
        if args.mcp:
            from agent.server import mcp
            mcp.run()
        else:
            import asyncio
            from agent.cli import main as cli_main
            asyncio.run(cli_main())
    except ImportError as e:
        print(f"Error: Required modules not found: {e}")
        print("Please ensure you have set up your virtual environment and installed requirements:")
        print("  python3 -m venv .venv")
        print("  source .venv/bin/activate")
        print("  pip install -r requirements.txt")
        sys.exit(1)

if __name__ == "__main__":
    main()
