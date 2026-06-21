import os
import subprocess
import re
import fnmatch
from typing import Dict, Any, List, Optional

# Base workspace directory to ensure operations stay relative/safe
WORKSPACE_DIR = os.path.abspath(os.getcwd())

def get_safe_path(path: str) -> str:
    """Resolve paths safely within the workspace directory."""
    # Handle absolute paths by keeping them if they are inside the workspace,
    # or prefixing relative paths with WORKSPACE_DIR.
    abs_path = os.path.abspath(os.path.join(WORKSPACE_DIR, path))
    # If the user tries to escape the workspace, we contain them for safety.
    if not abs_path.startswith(WORKSPACE_DIR):
        return os.path.abspath(WORKSPACE_DIR)
    return abs_path

def run_command(command: str) -> Dict[str, Any]:
    """
    Execute a shell command in the workspace directory.
    
    Args:
        command: The shell command to execute.
        
    Returns:
        A dictionary containing stdout, stderr, and the return code.
    """
    try:
        process = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            cwd=WORKSPACE_DIR,
            timeout=120  # Prevent hanging commands
        )
        return {
            "stdout": process.stdout,
            "stderr": process.stderr,
            "exit_code": process.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "Command timed out after 120 seconds.",
            "exit_code": -1
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error executing command: {str(e)}",
            "exit_code": -1
        }

def read_file(path: str, start_line: Optional[int] = 1, end_line: Optional[int] = None) -> Dict[str, Any]:
    """
    Read the contents of a file. Optionally, read a specific line range (1-indexed).
    
    Args:
        path: Path to the file.
        start_line: First line to read (1-indexed).
        end_line: Last line to read (inclusive, 1-indexed).
        
    Returns:
        A dictionary containing the content or error.
    """
    safe_path = get_safe_path(path)
    if not os.path.exists(safe_path):
        return {"error": f"File not found: {path}"}
    if os.path.isdir(safe_path):
        return {"error": f"Path is a directory, not a file: {path}"}
        
    try:
        with open(safe_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        start = max(1, start_line or 1) - 1
        end = min(total_lines, end_line or total_lines)
        
        selected_lines = lines[start:end]
        content = "".join(selected_lines)
        
        return {
            "content": content,
            "start_line": start + 1,
            "end_line": end,
            "total_lines": total_lines,
            "truncated": end < total_lines or start > 0
        }
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}

def write_file(path: str, content: str) -> Dict[str, Any]:
    """
    Create or completely overwrite a file with the given content.
    
    Args:
        path: Path to the file.
        content: Content to write.
        
    Returns:
        A dictionary indicating success or error.
    """
    safe_path = get_safe_path(path)
    try:
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"success": True, "message": f"Successfully wrote {len(content)} characters to {path}"}
    except Exception as e:
        return {"error": f"Error writing file: {str(e)}"}

def patch_file(path: str, search: str, replace: str) -> Dict[str, Any]:
    """
    Find a specific block of text in a file and replace it with new content.
    
    Args:
        path: Path to the file.
        search: The block of text to search for.
        replace: The block of text to replace it with.
        
    Returns:
        A dictionary indicating success or error.
    """
    safe_path = get_safe_path(path)
    if not os.path.exists(safe_path):
        return {"error": f"File not found: {path}"}
        
    try:
        with open(safe_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if search not in content:
            return {
                "error": "Search content not found in file. Ensure exact match including whitespace and indentation."
            }
            
        occurrences = content.count(search)
        if occurrences > 1:
            return {
                "error": f"Search content matches {occurrences} times. Please make your search block more specific to be unique."
            }
            
        new_content = content.replace(search, replace)
        with open(safe_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        return {"success": True, "message": f"Successfully patched file {path}"}
    except Exception as e:
        return {"error": f"Error patching file: {str(e)}"}

def list_dir(path: str = ".") -> Dict[str, Any]:
    """
    List contents of a directory.
    
    Args:
        path: The directory path to list.
        
    Returns:
        A list of files and directories with metadata.
    """
    safe_path = get_safe_path(path)
    if not os.path.exists(safe_path):
        return {"error": f"Directory not found: {path}"}
    if not os.path.isdir(safe_path):
        return {"error": f"Path is a file, not a directory: {path}"}
        
    try:
        items = []
        for name in os.listdir(safe_path):
            item_path = os.path.join(safe_path, name)
            is_dir = os.path.isdir(item_path)
            size = os.path.getsize(item_path) if not is_dir else 0
            items.append({
                "name": name,
                "is_dir": is_dir,
                "size_bytes": size
            })
            
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"items": items, "path": path}
    except Exception as e:
        return {"error": f"Error listing directory: {str(e)}"}

def search_grep(query: str, path: str = ".", case_insensitive: bool = True) -> Dict[str, Any]:
    """
    Search for a text pattern in files within the workspace directory (grep-like).
    
    Args:
        query: String or regex pattern to search for.
        path: Base path to search in.
        case_insensitive: Perform case-insensitive search.
        
    Returns:
        A dictionary containing list of matches with file, line number, and content.
    """
    safe_path = get_safe_path(path)
    matches = []
    max_matches = 100
    
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        pattern = re.compile(query, flags)
    except re.error:
        pattern = re.compile(re.escape(query), flags)
        
    try:
        for root, dirs, files in os.walk(safe_path):
            dirs[:] = [d for d in dirs if d not in ('.git', '.venv', 'node_modules', '__pycache__', 'dist', 'build')]
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, WORKSPACE_DIR)
                
                try:
                    with open(file_path, 'rb') as f:
                        if b'\x00' in f.read(1024):
                            continue
                            
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            if pattern.search(line):
                                matches.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "content": line.strip()
                                })
                                if len(matches) >= max_matches:
                                    return {"matches": matches, "limit_reached": True}
                except Exception:
                    continue
                    
        return {"matches": matches, "limit_reached": False}
    except Exception as e:
        return {"error": f"Error performing grep search: {str(e)}"}

def find_files(pattern: str, path: str = ".") -> Dict[str, Any]:
    """
    Find files matching a glob pattern (e.g. "*.py", "src/**/*.js").
    
    Args:
        pattern: The glob pattern to search for.
        path: Base path to start search.
        
    Returns:
        A list of matching file paths.
    """
    safe_path = get_safe_path(path)
    results = []
    
    try:
        for root, dirs, files in os.walk(safe_path):
            dirs[:] = [d for d in dirs if d not in ('.git', '.venv', 'node_modules', '__pycache__', 'dist', 'build')]
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, WORKSPACE_DIR)
                if fnmatch.fnmatch(file, pattern) or fnmatch.fnmatch(rel_path, pattern):
                    results.append(rel_path)
                    
        return {"files": sorted(results)}
    except Exception as e:
        return {"error": f"Error finding files: {str(e)}"}

# Mapping for direct access to functions
TOOLS_MAPPING = {
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
    "patch_file": patch_file,
    "list_dir": list_dir,
    "search_grep": search_grep,
    "find_files": find_files
}

# Declarations of tools in OpenAI format for function calling
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command in the workspace directory. Run tests, run compile, run checks, git commands, or any system CLI tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The exact shell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the workspace, with optional line range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read (relative or absolute within workspace)."
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Start line number (1-indexed). Defaults to 1."
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "End line number (inclusive, 1-indexed). Defaults to end of file."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or completely overwrite an existing file with the provided content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to create/overwrite."
                    },
                    "content": {
                        "type": "string",
                        "description": "Full text contents of the file."
                    }
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "patch_file",
            "description": "Update a file by finding a specific search string and replacing it. This is much more efficient than write_file for modifying parts of existing files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to modify."
                    },
                    "search": {
                        "type": "string",
                        "description": "The exact block of code/text to find in the file. Must be uniquely matched."
                    },
                    "replace": {
                        "type": "string",
                        "description": "The block of code/text to replace the search block with."
                    }
                },
                "required": ["path", "search", "replace"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the files and subdirectories in a directory path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to list. Use '.' for the current workspace root."
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_grep",
            "description": "Perform a recursive text/regex search in the workspace. Find function names, imports, variable usages, or text inside codebase files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text query or regex pattern to search for."
                    },
                    "path": {
                        "type": "string",
                        "description": "Base directory to start searching. Defaults to '.' (root of workspace)."
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Whether to perform case-insensitive search. Defaults to true."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Locate files matching a glob pattern (e.g., '*.py', 'src/**/*.js', 'config.json') in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "The glob pattern to match filenames against."
                    },
                    "path": {
                        "type": "string",
                        "description": "Base directory to start search. Defaults to '.'."
                    }
                },
                "required": ["pattern"]
            }
        }
    }
]
