import React, { useEffect, useState } from "react";
import { BrowserRouter as Router, Routes, Route, useNavigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import Login from "./components/Login";
import { api } from "./api";
import { supabase } from "../supabaseClient"; // make sure supabaseClient.js exists

function ChatPage() {
  const navigate = useNavigate();
  const [threads, setThreads] = useState([]);
  const [activeThread, setActiveThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [file, setFile] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [userTotalTokens, setUserTotalTokens] = useState(0);  // Total tokens across ALL threads

  useEffect(() => {
    const checkSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();

      if (!session?.access_token) {
        navigate("/login");
      } else {
        await loadThreads(session.access_token);
      }
    };

    checkSession();
  }, []);

  const loadThreads = async (token) => {
    try {
      let data = await api.getAllThreads(token);

      // ⚠️ Ensure threads is always an array
      if (!Array.isArray(data)) {
        console.warn("Threads data is not an array. Converting to empty array.");
        data = [];
      }

      // Token usage is fetched on-demand when a thread is selected (in handleSelectThread)
      // This avoids making N API calls on every page load
      setThreads(data);

      // Auto-select last active thread from localStorage if available
      const lastThreadId = localStorage.getItem('lastActiveThreadId');
      if (lastThreadId && data.length > 0) {
        const lastThread = data.find(t => t.thread_id === lastThreadId);
        if (lastThread) {
          // Trigger handleSelectThread to load messages and token usage
          handleSelectThread(lastThread);
        }
      }
    } catch (error) {
      console.error("Failed to load threads:", error);
      setThreads([]); // fallback to empty array
    }
  };



  // Helper to fetch TOTAL token usage for the user (across all threads)
  const fetchUserTotalTokens = async () => {
    try {
      const res = await api.getUserTotalTokenUsage();
      return res?.total_tokens || 0;
    } catch (err) {
      console.error("Failed to fetch user token usage:", err);
      return 0;
    }
  };


  const handleSelectThread = async (thread) => {
    setActiveThread(thread);
    setMessages([]);
    setFile(null);

    // Persist active thread ID to localStorage for refresh persistence
    if (thread?.thread_id) {
      localStorage.setItem('lastActiveThreadId', thread.thread_id);
    }

    // then fetch thread messages as before
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const data = await api.getThread(thread.thread_id, token);
      setMessages(Array.isArray(data?.messages) ? data.messages : []);

      // backend may include token_usage in the get_threads response
      if (data?.token_usage !== undefined) {
        setActiveThread(prev => ({
          ...prev,
          tokenUsage: data.token_usage,
          promptTokens: data.prompt_tokens ?? prev?.promptTokens,
          completionTokens: data.completion_tokens ?? prev?.completionTokens
        }));
      }
    } catch (error) {
      console.error("Failed to load thread details:", error);
      setMessages([]);
    }
  };


  // Fetch user total tokens on mount and poll every 5 seconds
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      const total = await fetchUserTotalTokens();
      if (!mounted) return;
      setUserTotalTokens(prev => (prev === total ? prev : total));
    };

    // Initial fetch
    poll();
    const id = setInterval(poll, 5000);
    return () => { mounted = false; clearInterval(id); };
  }, []);




  const handleNewChat = () => {
    setActiveThread(null);
    setMessages([]);
    setFile(null);
    // Clear persisted thread ID when starting new chat
    localStorage.removeItem('lastActiveThreadId');
  };

  const handleFileUpload = (newFile) => {
    setFile(newFile);
    if (newFile) {
      setActiveThread(null);
      setMessages([]);
    }
  };

  // Callback when a new thread is created - receives thread_id directly from SSE
  const handleNewThreadCreated = async (threadId) => {
    // Set as active thread immediately (no API call needed!)
    setActiveThread({ thread_id: threadId });

    // Refresh sidebar threads list in background
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      let data = await api.getAllThreads(token);
      if (Array.isArray(data)) setThreads(data);
    } catch (error) {
      console.error("Failed to refresh threads:", error);
    }
  };

  return (
    <div className="app-container">
      <Sidebar
        threads={threads}
        activeThreadId={activeThread?.thread_id}
        onSelectThread={handleSelectThread}
        onNewChat={handleNewChat}
        file={file}
        setFile={handleFileUpload}
        userTotalTokens={userTotalTokens}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      <ChatWindow
        activeThread={activeThread}
        messages={messages}
        onUpdateMessages={setMessages}
        file={file}
        onNewThreadCreated={handleNewThreadCreated}
        onStreamDone={async () => {
          // Refresh user total token usage after streaming completes
          const total = await fetchUserTotalTokens();
          setUserTotalTokens(total);
        }}
        isLimitReached={userTotalTokens >= 10000}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
      />
    </div>
  );
}

// App Component with Routing
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<ChatPage />} />
      </Routes>
    </Router>
  );
}

export default App;
