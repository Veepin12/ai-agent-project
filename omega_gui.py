#!/usr/bin/env python3
import sys
import os
import uvicorn
import webbrowser
import threading
import time

def open_browser():
    # Wait for the server to spin up
    time.sleep(1.5)
    url = "http://localhost:8000"
    print(f"\nOpening desktop console at {url}...\n")
    webbrowser.open(url)

def main():
    # Verify environment
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        print("Warning: No .env configuration found. Creating one from template.")
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            
    # Start browser opener in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start FastAPI server
    print("Starting Omega Agent Desktop Server on port 8000...")
    try:
        uvicorn.run("agent.gui_server:app", host="127.0.0.1", port=8000, log_level="info")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
