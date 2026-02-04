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

      setThreads(data);
    } catch (error) {
      console.error("Failed to load threads:", error);
      setThreads([]); // fallback to empty array
    }
  };

  const handleSelectThread = async (thread) => {
    setActiveThread(thread);
    setMessages([]);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const data = await api.getThread(thread.thread_id, token);

      // ⚠️ Ensure messages is always an array
      if (!Array.isArray(data?.messages)) {
        setMessages([]);
      } else {
        setMessages(data.messages);
      }
    } catch (error) {
      console.error("Failed to load thread details:", error);
      setMessages([]);
    }

    setFile(null);
  };

  const handleNewChat = () => {
    setActiveThread(null);
    setMessages([]);
    setFile(null);
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
        activeThread={activeThread}
      />

      <ChatWindow
        activeThread={activeThread}
        messages={messages}
        onUpdateMessages={setMessages}
        file={file}
        onNewThreadCreated={handleNewThreadCreated}
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
