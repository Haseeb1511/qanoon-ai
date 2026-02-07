import React, { useState, useRef } from 'react';
import {
    MessageSquare, Plus, Upload, X, File, LogOut, PanelLeftClose
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../../supabaseClient';
import logo from '../assets/gov_logo.png';
import './Sidebar.css';

const Sidebar = ({
    threads = [],               // List of chat threads
    activeThreadId,             // Currently selected thread id
    onSelectThread,             // Function to handle selecting a thread
    onNewChat,                  // Function to start a new chat
    file,                       // Current uploaded PDF file
    setFile,                    // Setter for PDF file
    userTotalTokens = 0,        // Total token usage across all threads for user
    isOpen = true,              // Sidebar open/collapsed state
    onToggle,                   // Toggle sidebar visibility
}) => {
    const navigate = useNavigate();
    const [isDragging, setIsDragging] = useState(false);  // For drag-drop PDF
    const fileInputRef = useRef(null);                   // File input reference

    // ----------------- Logout Handler -----------------
    const handleLogout = async () => {
        await supabase.auth.signOut();
        navigate('/login');
    };

    // ----------------- File Upload Handlers -----------------
    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile && droppedFile.type === 'application/pdf') {
            setFile(droppedFile);
        }
    };

    const showUploadSection = true; // Control whether upload section is visible

    return (
        <div className={`sidebar ${!isOpen ? 'sidebar-collapsed' : ''}`}>
            <div className="sidebar-inner">

                {/* ----------------- Sidebar Header ----------------- */}
                <div className="sidebar-header">
                    <div className="flex items-center gap-3 px-2">
                        <img src={logo} alt="QanoonAI" className="sidebar-logo" />
                    </div>
                    <button onClick={onToggle} className="sidebar-toggle-btn" title="Close sidebar">
                        <PanelLeftClose className="w-5 h-5" />
                    </button>
                </div>

                {/* ----------------- New Chat Button ----------------- */}
                <button onClick={onNewChat} className="new-chat-btn mb-6">
                    <Plus className="w-5 h-5" />
                    <span>New Chat</span>
                </button>

                {/* ----------------- Recent Threads ----------------- */}
                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    <div className="mb-4">
                        <h2 className="text-[11px] font-semibold text-[#676767] uppercase tracking-wider mb-3 px-3">
                            Recent
                        </h2>

                        {(!threads || threads.length === 0) ? (
                            <div className="px-3 py-4 text-center">
                                <span className="text-sm text-[#676767]">No chats yet</span>
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {threads.map((thread) => (
                                    <button
                                        key={thread.thread_id || thread.id} // fallback if thread_id missing
                                        onClick={() => onSelectThread(thread)}
                                        className={`thread-item ${activeThreadId === (thread.thread_id || thread.id) ? 'active' : ''}`}
                                    >
                                        <MessageSquare className="w-4 h-4" />
                                        <span className="truncate flex-1">{thread.preview || "Untitled Chat"}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* ----------------- Upload Section ----------------- */}
                <div className="upload-container">
                    <AnimatePresence>
                        {showUploadSection && (
                            <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                                className="overflow-hidden"
                            >
                                {!file ? (
                                    <div
                                        onDragOver={handleDragOver}
                                        onDragLeave={handleDragLeave}
                                        onDrop={handleDrop}
                                        onClick={() => fileInputRef.current?.click()}
                                        className={`dropzone ${isDragging ? 'bg-[#1f1f23]' : ''}`}
                                    >
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            accept=".pdf"
                                            onChange={handleFileChange}
                                            className="hidden"
                                        />
                                        <Upload className="w-5 h-5 mx-auto mb-2 text-[#676767]" />
                                        <p className="text-xs text-[#ececec]">Upload PDF</p>
                                    </div>
                                ) : (
                                    <div className="file-info">
                                        <File className="w-4 h-4 text-[#676767]" />
                                        <span className="truncate flex-1">{file.name}</span>
                                        <button onClick={() => setFile(null)} className="text-[#676767] hover:text-white">
                                            <X className="w-4 h-4" />
                                        </button>
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>


                {/* ----------------- Token Usage Display ----------------- */}
                <div className="token-usage-container px-4 py-2 border-t border-gray-700">
                    <div className="flex justify-between text-xs text-[#ececec] mb-1">
                        <span>Used: {userTotalTokens.toLocaleString()}</span>
                        <span>Limit: 10,000</span>
                    </div>
                    <div className="w-full h-2 bg-gray-600 rounded">
                        <div
                            className="h-2 bg-green-500 rounded"
                            style={{ width: `${Math.min((userTotalTokens / 10000) * 100, 100)}%` }}
                        />
                    </div>
                </div>


                {/* ----------------- Logout Button ----------------- */}
                <button onClick={handleLogout} className="logout-btn">
                    <LogOut className="w-4 h-4" />
                    <span>Sign Out</span>
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
