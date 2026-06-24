import React, { useState, useEffect, useRef } from "react";
import { 
  Play, Square, Terminal, ShieldAlert, Check, X, FileText, 
  Settings, Folder, Trash2, Plus, MessageSquare, Code, Compass,
  ChevronRight, RefreshCw, GitBranch, Cpu, Save, Mic, Volume2,
  VolumeX, GraduationCap, BarChart2, Edit3, Coffee, LogOut,
  HelpCircle, Globe, ArrowUpCircle, Download, Layout, ChevronDown,
  User, CheckSquare
} from "lucide-react";

export default function App() {
  // Multichat state
  const [chats, setChats] = useState(() => {
    const saved = localStorage.getItem("omega_chats");
    return saved ? JSON.parse(saved) : [
      { id: "default", title: "New chat", messages: [] }
    ];
  });
  const [currentChatId, setCurrentChatId] = useState(() => {
    const saved = localStorage.getItem("omega_chats");
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed.length > 0) return parsed[0].id;
    }
    return "default";
  });

  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState("code");
  const [model, setModel] = useState("llama-3.3-70b-versatile");
  const [extensions, setExtensions] = useState([]);
  const [files, setFiles] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState("");
  const [gitStatus, setGitStatus] = useState("");
  const [mcpConfig, setMcpConfig] = useState({});
  
  // Settings and Profile popup triggers
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [activeSettingsTab, setActiveSettingsTab] = useState("general");
  const [newMcp, setNewMcp] = useState({ name: "", command: "", args: "" });
  const [workspaceDir, setWorkspaceDir] = useState("ai-agent-project");
  
  // Active tool approvals list
  const [pendingApproval, setPendingApproval] = useState(null);
  
  // Connection & reasoning states
  const [wsConnected, setWsConnected] = useState(false);
  const [thinking, setThinking] = useState(false);
  
  // Voice Input/Output states
  const [isListening, setIsListening] = useState(false);
  const [voiceOutput, setVoiceOutput] = useState(false);
  
  const wsRef = useRef(null);
  const chatEndRef = useRef(null);
  const recognitionRef = useRef(null);
  const profileMenuRef = useRef(null);

  // Synchronize chat list to localStorage
  useEffect(() => {
    localStorage.setItem("omega_chats", JSON.stringify(chats));
  }, [chats]);

  // Load backend configurations
  useEffect(() => {
    connectWS();
    loadWorkspaceData();
    
    // Close menus on click outside
    const handleOutsideClick = (e) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(e.target)) {
        setShowProfileMenu(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);

    return () => {
      if (wsRef.current) wsRef.current.close();
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, []);

  // Scroll to bottom of message list on updates
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chats, currentChatId, thinking, pendingApproval]);

  const activeChat = chats.find(c => c.id === currentChatId) || chats[0] || { messages: [] };
  const messages = activeChat.messages || [];

  const connectWS = () => {
    const wsUrl = `ws://${window.location.hostname}:8000/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      console.log("WebSocket connected to agent backend");
    };

    ws.onclose = () => {
      setWsConnected(false);
      console.log("WebSocket disconnected. Retrying in 3s...");
      setTimeout(connectWS, 3000);
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      console.log("WS Message:", msg);

      switch (msg.type) {
        case "connection_established":
          setExtensions(msg.extensions || []);
          setMode(msg.mode || "code");
          setModel(msg.model || "");
          setWorkspaceDir(msg.workspace || "ai-agent-project");
          break;
          
        case "mode_changed":
          setMode(msg.mode);
          break;
          
        case "model_changed":
          setModel(msg.model);
          break;
          
        case "history_cleared":
          // Backend history cleared
          setThinking(false);
          setPendingApproval(null);
          break;
          
        case "callback":
          handleAgentCallback(msg.step_type, msg.name, msg.data);
          break;
          
        case "approval_request":
          setThinking(false);
          setPendingApproval({
            id: msg.id,
            tool_name: msg.tool_name,
            tool_args: msg.tool_args
          });
          break;
          
        case "chat_response":
          setThinking(false);
          setChats(prevChats => {
            return prevChats.map(c => {
              if (c.id === currentChatId) {
                const messages = c.messages || [];
                const lastMsg = messages[messages.length - 1];
                if (lastMsg && lastMsg.role === "assistant") {
                  return {
                    ...c,
                    messages: [
                      ...messages.slice(0, -1),
                      {
                        ...lastMsg,
                        content: msg.response,
                        isStreaming: false
                      }
                    ]
                  };
                } else {
                  return {
                    ...c,
                    messages: [
                      ...messages,
                      {
                        id: Date.now() + Math.random(),
                        role: "assistant",
                        content: msg.response,
                        isStreaming: false
                      }
                    ]
                  };
                }
              }
              return c;
            });
          });
          if (voiceOutput) {
            speakText(msg.response);
          }
          break;
          
        case "error":
          setThinking(false);
          addMessageToActiveChat({
            id: Date.now() + Math.random(),
            role: "system_error",
            content: msg.message
          });
          break;
          
        default:
          break;
      }
    };
  };

  const addMessageToActiveChat = (newMsg) => {
    setChats(prevChats => {
      return prevChats.map(c => {
        if (c.id === currentChatId) {
          let updatedTitle = c.title;
          // Auto name chat based on first user message
          if ((c.title === "New chat" || c.title === "") && newMsg.role === "user") {
            updatedTitle = newMsg.content.substring(0, 30) + (newMsg.content.length > 30 ? "..." : "");
          }
          return {
            ...c,
            title: updatedTitle,
            messages: [...(c.messages || []), newMsg]
          };
        }
        return c;
      });
    });
  };

  const appendChunkToLastAssistantMessage = (chunk) => {
    setChats(prevChats => {
      return prevChats.map(c => {
        if (c.id === currentChatId) {
          const messages = c.messages || [];
          const lastMsg = messages[messages.length - 1];
          if (lastMsg && lastMsg.role === "assistant" && lastMsg.isStreaming) {
            return {
              ...c,
              messages: [
                ...messages.slice(0, -1),
                {
                  ...lastMsg,
                  content: lastMsg.content + chunk
                }
              ]
            };
          } else {
            return {
              ...c,
              messages: [
                ...messages,
                {
                  id: Date.now() + Math.random(),
                  role: "assistant",
                  content: chunk,
                  isStreaming: true
                }
              ]
            };
          }
        }
        return c;
      });
    });
  };

  const handleAgentCallback = (stepType, name, data) => {
    if (stepType === "thinking") {
      setThinking(true);
    } else if (stepType === "content_chunk") {
      setThinking(false);
      appendChunkToLastAssistantMessage(data);
    } else if (stepType === "tool_call") {
      setThinking(false);
      addMessageToActiveChat({
        id: Date.now() + Math.random(),
        role: "tool_call",
        tool_name: name,
        args: data
      });
    } else if (stepType === "tool_response") {
      setThinking(true);
      addMessageToActiveChat({
        id: Date.now() + Math.random(),
        role: "tool_response",
        tool_name: name,
        response: data
      });
    }
  };

  const loadWorkspaceData = async () => {
    try {
      const filesRes = await fetch("http://localhost:8000/api/files");
      const filesData = await filesRes.json();
      setFiles(filesData.items || []);

      const gitRes = await fetch("http://localhost:8000/api/git/status");
      const gitData = await gitRes.json();
      setGitStatus(gitData.stdout || "Working tree clean.");

      const mcpRes = await fetch("http://localhost:8000/api/mcp");
      const mcpData = await mcpRes.json();
      setMcpConfig(mcpData);
    } catch (e) {
      console.error("Error loading workspace details", e);
    }
  };

  const sendPrompt = () => {
    if (!prompt.trim() || !wsConnected) return;

    addMessageToActiveChat({
      id: Date.now() + Math.random(),
      role: "user",
      content: prompt
    });

    wsRef.current.send(JSON.stringify({
      type: "chat_prompt",
      prompt: prompt
    }));

    setPrompt("");
    setThinking(true);
  };

  const approveTool = (approved) => {
    if (!pendingApproval || !wsConnected) return;
    
    wsRef.current.send(JSON.stringify({
      type: "approval_response",
      id: pendingApproval.id,
      approved: approved
    }));

    addMessageToActiveChat({
      id: Date.now() + Math.random(),
      role: "system",
      content: approved ? `✓ Approved tool call: ${pendingApproval.tool_name}` : `✗ Rejected tool call: ${pendingApproval.tool_name}`
    });

    setPendingApproval(null);
    setThinking(true);
  };

  const changeMode = (newMode) => {
    if (!wsConnected) return;
    wsRef.current.send(JSON.stringify({
      type: "change_mode",
      mode: newMode
    }));
  };

  const changeModel = (newModel) => {
    if (!wsConnected) return;
    wsRef.current.send(JSON.stringify({
      type: "change_model",
      model: newModel
    }));
  };

  const clearHistory = () => {
    if (!wsConnected) return;
    wsRef.current.send(JSON.stringify({
      type: "clear_history"
    }));
    
    // Clear in active chat session
    setChats(prev => {
      return prev.map(c => {
        if (c.id === currentChatId) {
          return { ...c, messages: [] };
        }
        return c;
      });
    });
  };

  const loadFile = async (name) => {
    try {
      setSelectedFile(name);
      const res = await fetch(`http://localhost:8000/api/file?path=${encodeURIComponent(name)}`);
      const data = await res.json();
      setFileContent(data.content || "");
    } catch (e) {
      setFileContent(`Error loading file: ${e.message}`);
    }
  };

  const saveFile = async () => {
    if (!selectedFile) return;
    try {
      const res = await fetch(`http://localhost:8000/api/file?path=${encodeURIComponent(selectedFile)}&content=${encodeURIComponent(fileContent)}`, {
        method: "POST"
      });
      if (res.ok) {
        alert("File saved successfully!");
      }
    } catch (e) {
      alert(`Save failed: ${e.message}`);
    }
  };

  const registerMcpServer = async () => {
    if (!newMcp.name || !newMcp.command) return;
    
    try {
      const res = await fetch("http://localhost:8000/api/mcp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newMcp.name,
          command: newMcp.command,
          args: newMcp.args ? newMcp.args.split(" ") : []
        })
      });
      if (res.ok) {
        setNewMcp({ name: "", command: "", args: "" });
        loadWorkspaceData();
        wsRef.current.send(JSON.stringify({ type: "change_mode", mode: mode }));
        alert("Extension connected successfully!");
      }
    } catch (e) {
      alert(`MCP Registration failed: ${e.message}`);
    }
  };

  const deleteMcpServer = async (name) => {
    try {
      const res = await fetch(`http://localhost:8000/api/mcp/${name}`, { method: "DELETE" });
      if (res.ok) {
        loadWorkspaceData();
      }
    } catch (e) {
      alert(`Failed to delete extension: ${e.message}`);
    }
  };

  // Multichat Actions
  const createNewChat = () => {
    const newId = Date.now().toString();
    const newChat = { id: newId, title: "New chat", messages: [] };
    setChats(prev => [newChat, ...prev]);
    setCurrentChatId(newId);
    clearHistory();
  };

  const deleteChat = (id, e) => {
    e.stopPropagation();
    setChats(prev => {
      const filtered = prev.filter(c => c.id !== id);
      if (filtered.length === 0) {
        return [{ id: "default", title: "New chat", messages: [] }];
      }
      return filtered;
    });
    if (currentChatId === id) {
      setTimeout(() => {
        setCurrentChatId(chats[0].id);
      }, 0);
    }
  };

  // HTML5 Speech Recognition (Speech to Text)
  const toggleListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Voice speech recognition is not supported in this browser. Please try Google Chrome or Safari.");
      return;
    }

    if (isListening) {
      if (recognitionRef.current) recognitionRef.current.stop();
      setIsListening(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognitionRef.current = recognition;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      const resultText = event.results[0][0].transcript;
      setPrompt(prev => prev + (prev ? " " : "") + resultText);
    };

    recognition.onerror = (event) => {
      console.error("Speech Recognition Error:", event.error);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognition.start();
  };

  // Browser Speech Synthesis (Text to Speech)
  const speakText = (text) => {
    if (!('speechSynthesis' in window)) return;
    
    // If already speaking, cancel/mute it
    if (window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      return;
    }

    // Clean text from markdown patterns
    const cleanText = text.replace(/[*#`_\-]/g, '').substring(0, 500); // speak first 500 chars for safety
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'en-US';
    window.speechSynthesis.speak(utterance);
  };

  const renderMarkdown = (text) => {
    if (!text) return null;
    
    // Split by code blocks (fenced by ```)
    const parts = text.split(/(```[\s\S]*?```)/g);
    
    return parts.map((part, idx) => {
      if (part.startsWith("```")) {
        // It's a code block
        const lines = part.split("\n");
        const header = lines[0].replace("```", "").trim();
        const codeLines = lines.slice(1, lines.length - 1);
        const code = codeLines.join("\n");
        
        if (header.toLowerCase() === "diff") {
          // Beautiful diff renderer
          return (
            <div key={idx} className="diff-block">
              <div className="diff-header">diff change block</div>
              <pre className="diff-pre">
                {codeLines.map((line, lIdx) => {
                  let lineClass = "";
                  if (line.startsWith("+")) lineClass = "diff-line-add";
                  else if (line.startsWith("-")) lineClass = "diff-line-del";
                  else lineClass = "diff-line-context";
                  
                  return (
                    <div key={lIdx} className={`diff-line ${lineClass}`}>
                      {line}
                    </div>
                  );
                })}
              </pre>
            </div>
          );
        } else {
          // Standard code block
          return (
            <div key={idx} className="code-block-container">
              {header && <div className="code-block-lang">{header}</div>}
              <pre className="code-block-pre">
                <code>{code}</code>
              </pre>
            </div>
          );
        }
      } else {
        // It's normal text, split by newlines for paragraph and list detection
        const lines = part.split("\n");
        return lines.map((line, lIdx) => {
          // Check for headers (e.g. #, ##, ###)
          if (line.startsWith("### ")) {
            return <h5 key={lIdx}>{line.replace("### ", "")}</h5>;
          } else if (line.startsWith("## ")) {
            return <h4 key={lIdx}>{line.replace("## ", "")}</h4>;
          } else if (line.startsWith("# ")) {
            return <h3 key={lIdx}>{line.replace("# ", "")}</h3>;
          }
          
          // Check for bullet list (e.g. - or *)
          if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
            const content = line.trim().replace(/^[-*]\s+/, "");
            return <li key={lIdx} style={{ marginLeft: "16px", listStyleType: "disc" }}>{renderInlineMarkdown(content)}</li>;
          }
          
          // Fallback to normal paragraph
          if (!line.trim()) return <div key={lIdx} style={{ height: "8px" }} />;
          return <p key={lIdx}>{renderInlineMarkdown(line)}</p>;
        });
      }
    });
  };

  const renderInlineMarkdown = (text) => {
    // Basic inline formatter for bold (**text**) and code (`code`)
    const boldRegex = /\*\*([\s\S]+?)\*\*/g;
    const codeRegex = /`([^`]+?)`/g;
    
    let parts = [{ type: 'text', content: text }];
    
    // Split by bold
    let tempParts = [];
    parts.forEach(p => {
      if (p.type === 'text') {
        const split = p.content.split(boldRegex);
        split.forEach((str, sIdx) => {
          tempParts.push({
            type: sIdx % 2 === 1 ? 'bold' : 'text',
            content: str
          });
        });
      } else {
        tempParts.push(p);
      }
    });
    parts = tempParts;
    
    // Split by inline code
    tempParts = [];
    parts.forEach(p => {
      if (p.type === 'text') {
        const split = p.content.split(codeRegex);
        split.forEach((str, sIdx) => {
          tempParts.push({
            type: sIdx % 2 === 1 ? 'code' : 'text',
            content: str
          });
        });
      } else {
        tempParts.push(p);
      }
    });
    parts = tempParts;
    
    return parts.map((p, idx) => {
      if (p.type === 'bold') {
        return <strong key={idx}>{p.content}</strong>;
      } else if (p.type === 'code') {
        return <code key={idx} className="inline-code">{p.content}</code>;
      }
      return p.content;
    });
  };

  const handleCategoryClick = (category) => {
    if (category === "code") {
      changeMode("code");
      setPrompt("Write code to implement ");
    } else if (category === "strategize") {
      changeMode("plan");
      setPrompt("Let's create an implementation plan for ");
    } else if (category === "learn") {
      changeMode("ask");
      setPrompt("Explain how this works: ");
    } else if (category === "write") {
      changeMode("code");
      setPrompt("Write documentation or comments describing ");
    } else if (category === "life") {
      changeMode("ask");
      setPrompt("Analyze the project structure and give suggestions for ");
    }
  };

  return (
    <div className="app-container">
      
      {/* Sidebar: Styled exactly like Claude Sidebar */}
      <div className="sidebar">
        
        {/* Top tab selector */}
        <div className="sidebar-top-tabs">
          <button className="tab-btn active">
            <MessageSquare size={16} />
            <span>Chat</span>
          </button>
          <button className="tab-btn" onClick={() => setSelectedFile("omega.py")}>
            <Layout size={16} />
          </button>
          <button className="tab-btn" onClick={() => { setActiveSettingsTab("mcp"); setShowSettingsModal(true); }}>
            <Code size={16} />
          </button>
        </div>

        {/* Action list */}
        <div className="sidebar-nav-list">
          <button onClick={createNewChat} className="nav-action-link">
            <Plus size={16} />
            <span>New chat</span>
          </button>
          <button className="nav-action-link" onClick={() => { setActiveSettingsTab("general"); setShowSettingsModal(true); }}>
            <Folder size={16} />
            <span>Projects</span>
          </button>
          <button className="nav-action-link" onClick={() => setSelectedFile(files[0]?.name || null)}>
            <Compass size={16} />
            <span>Artifacts</span>
          </button>
          <button className="nav-action-link" onClick={() => { setActiveSettingsTab("general"); setShowSettingsModal(true); }}>
            <Settings size={16} />
            <span>Customize</span>
          </button>
        </div>

        {/* Recents chat history list */}
        <div className="sidebar-recents-section">
          <span className="recents-header-title">Recents</span>
          <div className="recents-list">
            {chats.map(c => (
              <div 
                key={c.id} 
                onClick={() => selectChat(c.id)}
                className={`recent-item-row ${currentChatId === c.id ? 'active' : ''}`}
              >
                <span className="recent-item-title">{c.title || "New chat"}</span>
                {chats.length > 1 && (
                  <button onClick={(e) => deleteChat(c.id, e)} className="recent-item-delete" title="Delete chat">
                    <Trash2 size={12} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>



        {/* Bottom Profile Section matching Claude */}
        <div className="sidebar-profile-footer" ref={profileMenuRef}>
          <div className="profile-badge-row" onClick={() => setShowProfileMenu(!showProfileMenu)}>
            <div className="profile-avatar">vc</div>
            <span className="profile-name">veepin chaudhar</span>
            <ChevronDown size={14} className="profile-chevron" />
          </div>
          <button className="install-desktop-btn" title="Get apps" onClick={() => alert("Omega Agent is fully installed on this Mac.")}>
            <Download size={14} />
          </button>

          {/* Profile Menu Popover Dropdown */}
          {showProfileMenu && (
            <div className="profile-popover-menu">
              <div className="popover-email-header">veepinchaudhary001@gmail.com</div>
              
              <button onClick={() => { setShowProfileMenu(false); setActiveSettingsTab("general"); setShowSettingsModal(true); }} className="popover-item">
                <Settings size={14} />
                <span className="popover-text">Settings</span>
                <span className="popover-hotkey">⌘,</span>
              </button>
              
              <button onClick={() => { setShowProfileMenu(false); setActiveSettingsTab("voice"); setShowSettingsModal(true); }} className="popover-item">
                <Globe size={14} />
                <span className="popover-text">Language & Voice</span>
              </button>

              <button onClick={() => alert("Visit github.com/Veepin12/ai-agent-project for help")} className="popover-item">
                <HelpCircle size={14} />
                <span className="popover-text">Get help</span>
              </button>

              <div className="popover-divider" />

              <button onClick={() => alert("Omega is currently running on Enterprise Developer Mode.")} className="popover-item upgrade-highlight">
                <ArrowUpCircle size={14} />
                <span className="popover-text">Upgrade plan</span>
              </button>

              <button onClick={() => { setShowProfileMenu(false); setActiveSettingsTab("mcp"); setShowSettingsModal(true); }} className="popover-item">
                <Download size={14} />
                <span className="popover-text">Get extensions (MCP)</span>
              </button>

              <button onClick={() => alert("Omega Agent Core v1.0.0 built on Groq API.")} className="popover-item">
                <HelpCircle size={14} />
                <span className="popover-text">Learn more</span>
              </button>

              <div className="popover-divider" />

              <button onClick={() => { setShowProfileMenu(false); clearHistory(); }} className="popover-item logout-red">
                <LogOut size={14} />
                <span className="popover-text">Log out (Clear)</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main Conversation Canvas */}
      <div className="main-content">
        
        {/* Top Header Row details */}
        <div className="header">
          <div className="header-title-group">
            <Cpu className="cpu-icon text-glow" size={16} />
            <h1 className="header-title">Omega Agent Console</h1>
            <div className={`status-indicator ${wsConnected ? "connected" : "disconnected"}`} />
          </div>
          <div className="header-actions">
            <div className="plan-upgrade-label">Free plan · <span onClick={() => alert("Upgraded to developer pro")} className="upgrade-link">Upgrade</span></div>
            <select 
              value={model} 
              onChange={(e) => changeModel(e.target.value)}
              className="model-select"
            >
              <optgroup label="Gemini Models">
                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
              </optgroup>
              <optgroup label="Groq Models">
                <option value="llama-3.3-70b-versatile">Llama 3.3 70B</option>
                <option value="mixtral-8x7b-32768">Mixtral 8x7B</option>
                <option value="gemma2-9b-it">Gemma 2 9B</option>
              </optgroup>
              <optgroup label="OpenAI Models">
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4o-mini">GPT-4o Mini</option>
              </optgroup>
            </select>
          </div>
        </div>

        {/* Message scroll viewport */}
        <div className="chat-container">
          {messages.length === 0 ? (
            /* Welcome View matching Claude Web exactly */
            <div className="claude-welcome-view">
              <div className="claude-logo-icon">✻</div>
              <h2 className="claude-serif-title">What shall we think through?</h2>
              
              {/* Central Claude input card */}
              <div className="claude-input-card">
                <textarea 
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendPrompt();
                    }
                  }}
                  placeholder="How can I help you today?"
                  disabled={!wsConnected || thinking || pendingApproval}
                  className="card-textarea"
                />
                <div className="card-controls-row">
                  <div className="card-left-actions">
                    <button className="card-circle-btn" onClick={() => loadWorkspaceData()} title="Refresh context files">
                      <Plus size={16} />
                    </button>
                    <div className="card-active-mode-pill">
                      Mode: <span className="mode-highlight">{mode}</span>
                    </div>
                  </div>
                  <div className="card-right-actions">
                    <span className="card-model-label">Claude 3.5 Sonnet</span>
                    
                    <button 
                      onClick={toggleListening} 
                      className={`card-circle-btn voice-btn ${isListening ? 'listening pulsing' : ''}`}
                      title={isListening ? "Listening... click to stop" : "Start speaking voice input"}
                    >
                      <Mic size={15} />
                    </button>

                    <button 
                      onClick={() => {
                        setVoiceOutput(!voiceOutput);
                        if (messages.length > 0) {
                          // Speak last assistant message
                          const lastAssistant = [...messages].reverse().find(m => m.role === "assistant");
                          if (lastAssistant) speakText(lastAssistant.content);
                        } else {
                          speakText("Voice response mode toggled");
                        }
                      }}
                      className={`card-circle-btn voice-btn ${voiceOutput ? 'voice-active' : ''}`}
                      title="Toggle text-to-speech output voice feedback"
                    >
                      <Volume2 size={15} />
                    </button>

                    <button 
                      onClick={sendPrompt}
                      disabled={!wsConnected || !prompt.trim() || thinking || pendingApproval}
                      className="card-send-btn"
                    >
                      <Play size={14} fill="currentColor" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Lower suggestion category pills */}
              <div className="category-pill-row">
                <button onClick={() => handleCategoryClick("code")} className="category-pill">
                  <Code size={14} />
                  <span>Code</span>
                </button>
                <button onClick={() => handleCategoryClick("learn")} className="category-pill">
                  <GraduationCap size={14} />
                  <span>Learn</span>
                </button>
                <button onClick={() => handleCategoryClick("strategize")} className="category-pill">
                  <BarChart2 size={14} />
                  <span>Strategize</span>
                </button>
                <button onClick={() => handleCategoryClick("write")} className="category-pill">
                  <Edit3 size={14} />
                  <span>Write</span>
                </button>
                <button onClick={() => handleCategoryClick("life")} className="category-pill">
                  <Coffee size={14} />
                  <span>Life stuff</span>
                </button>
              </div>
            </div>
          ) : (
            /* Active message logs wrapper */
            <div className="active-chat-stream">
              {messages.map((msg, index) => {
                if (msg.role === "user") {
                  return (
                    <div key={index} className="chat-row user-row">
                      <div className="message-bubble message-user">
                        <p className="bubble-label">You</p>
                        <div className="bubble-text markdown-body">
                          {renderMarkdown(msg.content)}
                        </div>
                      </div>
                    </div>
                  );
                } else if (msg.role === "assistant") {
                  return (
                    <div key={index} className="chat-row assistant-row">
                      <div className="message-bubble message-assistant">
                        <p className="bubble-label assistant-label">
                          <Cpu size={12} /> Omega Agent
                        </p>
                        <div className="bubble-text markdown-body">
                          {renderMarkdown(msg.content)}
                        </div>
                      </div>
                    </div>
                  );
                } else if (msg.role === "tool_call") {
                  return (
                    <div key={index} className="chat-row tool-row">
                      <div className="message-tool-call">
                        <Terminal size={14} className="tool-icon" />
                        <div className="tool-details">
                          <p className="tool-title">Executing Tool: {msg.tool_name}</p>
                          <pre className="tool-arguments">{JSON.stringify(msg.args, null, 2)}</pre>
                        </div>
                      </div>
                    </div>
                  );
                } else if (msg.role === "tool_response") {
                  return (
                    <div key={index} className="chat-row tool-row">
                      <div className="message-tool-response">
                        <Check size={14} className="tool-success-icon" />
                        <div className="tool-details">
                          <p className="tool-title text-success">Tool Success: {msg.tool_name}</p>
                          <pre className="tool-result-pre">{msg.response}</pre>
                        </div>
                      </div>
                    </div>
                  );
                } else if (msg.role === "system") {
                  return (
                    <div key={index} className="chat-row system-row">
                      <span className="system-pill">{msg.content}</span>
                    </div>
                  );
                } else if (msg.role === "system_error") {
                  return (
                    <div key={index} className="chat-row system-row">
                      <div className="system-error-bubble">
                        <ShieldAlert size={14} className="error-icon" />
                        <div>
                          <p className="error-title">Error</p>
                          <p className="error-text">{msg.content}</p>
                        </div>
                      </div>
                    </div>
                  );
                }
                return null;
              })}

              {/* Interactive Approvals overlay card */}
              {pendingApproval && (
                <div className="chat-row approval-row">
                  <div className="approval-panel pulse-glow-yellow">
                    <div className="approval-header">
                      <ShieldAlert size={18} />
                      <span>Approval Requested</span>
                    </div>
                    <p className="approval-description">
                      The agent requires confirmation to run this mutating/execution tool call on your workspace:
                    </p>
                    <pre className="approval-code-pre">
                      {pendingApproval.tool_name}({JSON.stringify(pendingApproval.tool_args, null, 2)})
                    </pre>
                    <div className="approval-actions">
                      <button onClick={() => approveTool(true)} className="approve-action-btn">
                        <Check size={14} /> Approve Action
                      </button>
                      <button onClick={() => approveTool(false)} className="deny-action-btn">
                        <X size={14} /> Deny Action
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Thinking loader */}
              {thinking && (
                <div className="chat-row assistant-row">
                  <div className="thinking-indicator">
                    <RefreshCw className="animate-spin" size={12} />
                    <span>Omega is processing...</span>
                  </div>
                </div>
              )}
              
              <div ref={chatEndRef} />
            </div>
          )}
        </div>

        {/* Bottom Pinned Card Input for active chats */}
        {messages.length > 0 && (
          <div className="active-chat-input-area">
            <div className="claude-input-card active-card">
              <textarea 
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    sendPrompt();
                  }
                }}
                placeholder="How can I help you today?"
                disabled={!wsConnected || thinking || pendingApproval}
                className="card-textarea"
              />
              <div className="card-controls-row">
                <div className="card-left-actions">
                  <button className="card-circle-btn" onClick={() => loadWorkspaceData()} title="Refresh context files">
                    <Plus size={16} />
                  </button>
                  <div className="mode-tab-bar">
                    {['ask', 'plan', 'code'].map(m => (
                      <button 
                        key={m} 
                        onClick={() => changeMode(m)}
                        className={`mode-tab-btn ${mode === m ? 'active' : ''}`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="card-right-actions">
                  
                  <button 
                    onClick={toggleListening} 
                    className={`card-circle-btn voice-btn ${isListening ? 'listening pulsing' : ''}`}
                    title={isListening ? "Listening... click to stop" : "Start speaking voice input"}
                  >
                    <Mic size={15} />
                  </button>

                  <button 
                    onClick={() => {
                      setVoiceOutput(!voiceOutput);
                      if (messages.length > 0) {
                        const lastAssistant = [...messages].reverse().find(m => m.role === "assistant");
                        if (lastAssistant) speakText(lastAssistant.content);
                      }
                    }}
                    className={`card-circle-btn voice-btn ${voiceOutput ? 'voice-active' : ''}`}
                    title="Toggle text-to-speech output voice feedback"
                  >
                    <Volume2 size={15} />
                  </button>

                  <button 
                    onClick={sendPrompt}
                    disabled={!wsConnected || !prompt.trim() || thinking || pendingApproval}
                    className="card-send-btn"
                  >
                    <Play size={14} fill="currentColor" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Right Side: Local File Viewer & Editor */}
      {selectedFile && (
        <div className="editor-panel">
          <div className="editor-header">
            <div className="editor-file-info">
              <FileText size={15} className="editor-icon" />
              <span className="editor-filename">{selectedFile}</span>
            </div>
            <div className="editor-actions-group">
              <button onClick={() => setSelectedFile(null)} className="editor-close-btn" title="Close editor">
                <X size={15} />
              </button>
            </div>
          </div>
          <textarea 
            value={fileContent}
            readOnly
            className="editor-textarea"
          />
        </div>
      )}

      {/* Settings Modal (Toggled from profile menu) */}
      {showSettingsModal && (
        <div className="modal-overlay">
          <div className="settings-modal-content glass-panel">
            <div className="settings-modal-header">
              <h3>Settings</h3>
              <button onClick={() => setShowSettingsModal(false)} className="modal-close-btn">
                <X size={18} />
              </button>
            </div>
            
            <div className="settings-modal-body">
              {/* Left sidebar tab list */}
              <div className="settings-tabs-list">
                <button 
                  onClick={() => setActiveSettingsTab("general")} 
                  className={`settings-tab-btn ${activeSettingsTab === "general" ? "active" : ""}`}
                >
                  General Settings
                </button>
                <button 
                  onClick={() => setActiveSettingsTab("mcp")} 
                  className={`settings-tab-btn ${activeSettingsTab === "mcp" ? "active" : ""}`}
                >
                  MCP Extensions
                </button>
                <button 
                  onClick={() => setActiveSettingsTab("voice")} 
                  className={`settings-tab-btn ${activeSettingsTab === "voice" ? "active" : ""}`}
                >
                  Language & Voice
                </button>
              </div>

              {/* Right panel layout content */}
              <div className="settings-tab-content">
                {activeSettingsTab === "general" && (
                  <div className="settings-pane">
                    <h4 className="pane-title">General Application Settings</h4>
                    
                    <div className="form-group">
                      <label>Workspace Directory</label>
                      <input 
                        type="text" 
                        readOnly 
                        value={workspaceDir}
                      />
                      <span className="field-hint">Current working root directory served by FastAPI backend.</span>
                    </div>
                    
                    <div className="form-group">
                      <label>Model Engine</label>
                      <select 
                        value={model} 
                        onChange={(e) => changeModel(e.target.value)}
                      >
                        <option value="gemini-2.5-flash">Gemini 2.5 Flash (Google AI Studio)</option>
                        <option value="gemini-2.5-pro">Gemini 2.5 Pro (Google AI Studio)</option>
                        <option value="gemini-1.5-flash">Gemini 1.5 Flash (Google AI Studio)</option>
                        <option value="gemini-1.5-pro">Gemini 1.5 Pro (Google AI Studio)</option>
                        <option value="llama-3.3-70b-versatile">Llama 3.3 70B (Groq Cloud)</option>
                        <option value="mixtral-8x7b-32768">Mixtral 8x7B (Groq Cloud)</option>
                        <option value="gemma2-9b-it">Gemma 2 9B (Groq Cloud)</option>
                        <option value="gpt-4o">GPT-4o (OpenAI)</option>
                        <option value="gpt-4o-mini">GPT-4o Mini (OpenAI)</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>Dangerous Tools Approval Mode</label>
                      <div className="checkbox-row">
                        <CheckSquare size={16} className="text-success" />
                        <span>Interactive Prompt for `run_command`, `write_file`, and `patch_file`</span>
                      </div>
                    </div>

                    <div className="form-group mt-auto">
                      <button onClick={clearHistory} className="pane-btn-danger">
                        Clear Current Session Messages
                      </button>
                    </div>
                  </div>
                )}

                {activeSettingsTab === "mcp" && (
                  <div className="settings-pane">
                    <h4 className="pane-title">Model Context Protocol (MCP) Extensions</h4>
                    <p className="pane-description">Connect external MCP servers to inject new tools into the reasoning loop.</p>
                    
                    {/* Add MCP Form */}
                    <div className="mcp-register-form">
                      <div className="form-row">
                        <input 
                          type="text" 
                          placeholder="Server Name (e.g. filesystem)"
                          value={newMcp.name}
                          onChange={(e) => setNewMcp(prev => ({ ...prev, name: e.target.value }))}
                        />
                        <input 
                          type="text" 
                          placeholder="Launch Command (e.g. npx)"
                          value={newMcp.command}
                          onChange={(e) => setNewMcp(prev => ({ ...prev, command: e.target.value }))}
                        />
                      </div>
                      <input 
                        type="text" 
                        placeholder="Arguments (e.g. -y @modelcontextprotocol/server-filesystem /path)"
                        value={newMcp.args}
                        onChange={(e) => setNewMcp(prev => ({ ...prev, args: e.target.value }))}
                        className="mt-8"
                      />
                      <button onClick={registerMcpServer} className="pane-btn-primary mt-12">
                        Connect Extension
                      </button>
                    </div>

                    {/* Active MCP list */}
                    <div className="active-extensions-list">
                      <label>Connected Extensions ({Object.keys(mcpConfig).length})</label>
                      {Object.keys(mcpConfig).length === 0 ? (
                        <p className="empty-text">No external servers registered.</p>
                      ) : (
                        <div className="mcp-table">
                          {Object.entries(mcpConfig).map(([name, cfg]) => (
                            <div key={name} className="mcp-row-item">
                              <div className="mcp-meta">
                                <span className="mcp-meta-name">{name}</span>
                                <span className="mcp-meta-cmd">{cfg.command} {cfg.args?.join(" ")}</span>
                              </div>
                              <button onClick={() => deleteMcpServer(name)} className="mcp-meta-delete" title="Disconnect Extension">
                                <Trash2 size={13} />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {activeSettingsTab === "voice" && (
                  <div className="settings-pane">
                    <h4 className="pane-title">Language & Voice Input/Output</h4>
                    
                    <div className="form-group">
                      <label>Primary Speech Language</label>
                      <select defaultValue="en-US">
                        <option value="en-US">English (United States)</option>
                        <option value="en-GB">English (United Kingdom)</option>
                        <option value="es-ES">Español (España)</option>
                        <option value="fr-FR">Français (France)</option>
                        <option value="de-DE">Deutsch (Deutschland)</option>
                      </select>
                    </div>

                    <div className="form-group">
                      <label>Voice Synthesis Volume</label>
                      <div className="voice-volume-preview">
                        <Volume2 size={16} className="text-muted" />
                        <input type="range" min="0" max="1" step="0.1" defaultValue="0.8" className="voice-slider" />
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Text to Speech Status</label>
                      <div className={`voice-status-badge ${voiceOutput ? 'active' : ''}`} onClick={() => setVoiceOutput(!voiceOutput)}>
                        {voiceOutput ? "✓ Automatic Speech Synthesis Enabled" : "✗ Voice Output Muted"}
                      </div>
                    </div>

                    <div className="voice-help-card">
                      <h5>Speech Recognition Hint</h5>
                      <p>Click the microphone icon inside the text input box to record your voice input. Click again or pause to transcribe.</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
