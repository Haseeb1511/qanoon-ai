import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import { api } from './api';

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

  const handleSelectThread = async (thread) => {
    setActiveThread(thread);
    setMessages([]); // Clear previous messages while loading
    try {
      const data = await api.getThread(thread.thread_id);
      setMessages(data.messages || []);
    } catch (error) {
      console.error("Failed to load thread details:", error);
    }
  };

  const handleNewChat = () => {
    setActiveThread(null);
    setMessages([]);
  };

  return (
    <div className="flex w-full h-screen bg-[var(--bg-primary)] text-[var(--text-primary)]">
      <Sidebar
        threads={threads}
        activeThreadId={activeThread?.thread_id}
        onSelectThread={handleSelectThread}
        onNewChat={handleNewChat}
        file={file}
        setFile={setFile}
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