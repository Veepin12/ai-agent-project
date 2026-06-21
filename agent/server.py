import json
from typing import Optional
from fastmcp import FastMCP
from agent import tools

# Initialize the FastMCP server
mcp = FastMCP("OmegaCode")

@mcp.tool()
def execute_command(command: str) -> str:
    """
    Execute a shell command in the workspace directory. 
    Use this to run tests, compile files, perform git actions, or invoke local scripts.
    """
    result = tools.run_command(command)
    return json.dumps(result, indent=2)

@mcp.tool()
def view_file_content(path: str, start_line: Optional[int] = 1, end_line: Optional[int] = None) -> str:
    """
    Read the contents of a file in the workspace.
    Supports reading specific line ranges (1-indexed).
    """
    result = tools.read_file(path, start_line=start_line, end_line=end_line)
    return json.dumps(result, indent=2)

@mcp.tool()
def write_file_content(path: str, content: str) -> str:
    """
    Create a new file or completely overwrite an existing file with the provided content.
    """
    result = tools.write_file(path, content)
    return json.dumps(result, indent=2)

@mcp.tool()
def patch_file_content(path: str, search: str, replace: str) -> str:
    """
    Update a file by finding a specific search string and replacing it.
    This is highly efficient and preferred over write_file_content for small/medium edits.
    """
    result = tools.patch_file(path, search, replace)
    return json.dumps(result, indent=2)

@mcp.tool()
def list_directory(path: str = ".") -> str:
    """
    List the files and subdirectories in a directory path.
    """
    result = tools.list_dir(path)
    return json.dumps(result, indent=2)

@mcp.tool()
def search_grep_code(query: str, path: str = ".") -> str:
    """
    Perform a recursive text/regex search in the workspace.
    Find function names, imports, variable usages, or text inside codebase files.
    """
    result = tools.search_grep(query, path)
    return json.dumps(result, indent=2)

@mcp.tool()
def find_files_matching(pattern: str, path: str = ".") -> str:
    """
    Locate files matching a glob pattern (e.g., '*.py', 'src/**/*.js', 'config.json') in the workspace.
    """
    result = tools.find_files(pattern, path)
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    # When run directly, start the MCP server
    mcp.run()
