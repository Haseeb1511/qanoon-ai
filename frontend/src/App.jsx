
import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import { api } from './api';

function App() {
  const [threads, setThreads] = useState([]);
  const [activeThread, setActiveThread] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
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
    setLoading(true);
    setMessages([]); // Clear previous messages while loading
    try {
      const data = await api.getThread(thread.thread_id);
      setMessages(data.messages || []);
    } catch (error) {
      console.error("Failed to load thread details:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setActiveThread(null);
    setMessages([]);
  };

  const handleSendMessage = async (text) => {
    if (!activeThread) return;

    // Optimistic Update
    const newMsg = { role: 'human', content: text };
    setMessages(prev => [...prev, newMsg]);
    setLoading(true);

    try {
      const response = await api.followUp(activeThread.doc_id, activeThread.thread_id, text);
      const aiMsg = { role: 'ai', content: response.result };
      setMessages(prev => [...prev, aiMsg]);

      // Update preview in sidebar if needed (optional, simplistic here)
    } catch (error) {
      console.error("Failed to send message:", error);
      setMessages(prev => [...prev, { role: 'ai', content: "Error: Failed to get response." }]);
    } finally {
      setLoading(false);
    }
  };

  const handleUploadAndAsk = async (uploadedFile, question) => {
    setLoading(true);
    // Optimistic Update
    const newMsg = { role: 'human', content: question };
    setMessages([newMsg]);

    try {
      const response = await api.askQuestion(uploadedFile, question);
      const aiMsg = { role: 'ai', content: response.answer };
      setMessages(prev => [...prev, aiMsg]);

      // Set as active thread
      const newThread = {
        thread_id: response.thread_id,
        doc_id: response.doc_id,
        preview: question.substring(0, 50) + "..."
      };

      setActiveThread(newThread);
      setThreads(prev => [newThread, ...prev]);
      setFile(null); // Clear file after successful upload

    } catch (error) {
      console.error("Failed to upload and ask:", error);
      setMessages(prev => [...prev, { role: 'ai', content: "Error: Failed to process request." }]);
    } finally {
      setLoading(false);
    }
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
        onSendMessage={handleSendMessage}
        onUploadAndAsk={handleUploadAndAsk}
        loading={loading}
        file={file}
      />
    </div>
  );
}

export default App;
