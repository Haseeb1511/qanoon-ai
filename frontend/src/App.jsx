import React, { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import { api } from "./api";

function App() {
  const [threads, setThreads] = useState([]);
  const [activeThread, setActiveThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [file, setFile] = useState(null);

  // Load threads on mount
  useEffect(() => {
    loadThreads();
  }, []);

  const loadThreads = async () => {
    try {
      const data = await api.getAllThreads();
      setThreads(data || []);
    } catch (error) {
      console.error("Failed to load threads:", error);
    }
  };

  // When user clicks a thread
  const handleSelectThread = async (thread) => {
    setActiveThread(thread);
    setMessages([]); // Clear UI while loading messages

    try {
      const data = await api.getThread(thread.thread_id);
      setMessages(data.messages || []);
    } catch (error) {
      console.error("Failed to load thread details:", error);
    }

    // ❗ Keep file upload enabled even when selecting thread
    setFile(null);
  };

  // When user clicks NEW CHAT
  const handleNewChat = () => {
    setActiveThread(null);
    setMessages([]);
    setFile(null); // allow new file upload
  };

  // When user uploads a new PDF - clear chat and start fresh
  const handleFileUpload = (newFile) => {
    setFile(newFile);
    if (newFile) {
      // Clear active thread and messages to start fresh chat
      setActiveThread(null);
      setMessages([]);
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
      />

    </div>
  );
}

export default App;
