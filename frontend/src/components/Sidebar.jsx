import React, { useState, useRef } from 'react';
import { MessageSquare, Plus, FileText, Upload, X, File } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import logo from '../assets/gov_logo.png';

import './Sidebar.css';

const Sidebar = ({ threads, activeThreadId, onSelectThread, onNewChat, file, setFile, activeThread }) => {
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef(null);

    const handleFileChange = (e) => {
        if (e.target.files[0]) {
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

    // Always show upload section so users can upload new PDFs anytime
    const showUploadSection = true;

    return (
        <div className="sidebar">
            <div className="sidebar-inner">
                <div className="flex items-center gap-3 mb-6 px-2">
                    <img src={logo} alt="QanoonAI" className="sidebar-logo" />
                    {/* <span className="font-bold text-lg text-white">QanoonAI</span> */}
                </div>

                <button onClick={onNewChat} className="new-chat-btn mb-6">
                    <Plus className="w-5 h-5" />
                    <span>New Chat</span>
                </button>

                <div className="flex-1 overflow-y-auto custom-scrollbar">
                    <div className="mb-4">
                        <h2 className="text-[11px] font-semibold text-[#676767] uppercase tracking-wider mb-3 px-3">
                            Recent
                        </h2>
                        {threads.length === 0 ? (
                            <div className="px-3 py-4 text-center">
                                <span className="text-sm text-[#676767]">No chats yet</span>
                            </div>
                        ) : (
                            <div className="space-y-1">
                                {threads.map((thread) => (
                                    <button
                                        key={thread.thread_id}
                                        onClick={() => onSelectThread(thread)}
                                        className={`thread-item ${activeThreadId === thread.thread_id ? 'active' : ''}`}
                                    >
                                        <MessageSquare className="w-4 h-4" />
                                        <span className="truncate flex-1">{thread.preview || "Untitled Chat"}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

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
            </div>
        </div>
    );
};

export default Sidebar;
