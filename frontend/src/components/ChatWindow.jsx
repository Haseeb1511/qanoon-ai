import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, Loader2, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

const ChatWindow = ({
    activeThread,
    messages,
    onSendMessage,
    onUploadAndAsk,
    loading,
    file
}) => {
    const [input, setInput] = useState("");
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, loading]);

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
        }
    }, [input]);

    const handleSubmit = (e) => {
        e.preventDefault();
        if (loading) return;

        if (!activeThread) {
            if (!file || !input.trim()) return;
            onUploadAndAsk(file, input);
        } else {
            if (!input.trim()) return;
            onSendMessage(input);
        }
        setInput("");
        if (textareaRef.current) textareaRef.current.style.height = 'auto';
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };

    const canSendMessage = activeThread || file;

    return (
        <div className="chat-container">
            <div className="chat-main custom-scrollbar">
                <div className="chat-inner">
                    {!activeThread && messages.length === 0 ? (
                        <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
                            <h1 className="text-3xl font-bold mb-4">How can I help you?</h1>
                            <p className="text-secondary max-w-md mb-8">
                                {file ? `"${file.name}" is ready. Ask me anything.` : "Upload a legal document to get started."}
                            </p>
                            {!file && (
                                <div className="flex flex-wrap justify-center gap-2">
                                    {/* {['Analyze contracts', 'Explain legal jargon', 'Find clauses'].map((s) => (
                                        <div key={s} className="px-3 py-1.5 rounded-lg border border-[#2a2a2e] text-sm text-[#676767] hover:border-white/20 transition-colors">
                                            {s}
                                        </div>
                                    ))} */}
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="flex flex-col">
                            {messages.map((msg, idx) => (
                                <motion.div
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    key={idx}
                                    className={`message-bubble ${msg.role === 'human' ? 'user' : 'ai'}`}
                                >
                                    {msg.content}
                                </motion.div>
                            ))}
                            {loading && (
                                <div className="message-bubble ai italic text-[#676767]">
                                    Thinking...
                                </div>
                            )}
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            <div className="input-area">
                <div className="input-wrapper">
                    <textarea
                        ref={textareaRef}
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Message QanoonAI..."
                        rows={1}
                        disabled={loading || !canSendMessage}
                        className="chat-textarea"
                    />
                    <button
                        onClick={handleSubmit}
                        disabled={loading || !input.trim() || !canSendMessage}
                        className="send-btn"
                    >
                        {loading ? <Loader2 className="w-4 h-4 animate-spin text-black" /> : <Send className="w-4 h-4 text-black" />}
                    </button>
                </div>
                <p className="text-center text-[10px] text-[#676767] mt-3">
                    QanoonAI Developed by Haseeb Manzoor.
                </p>
            </div>
        </div>
    );
};

export default ChatWindow;
