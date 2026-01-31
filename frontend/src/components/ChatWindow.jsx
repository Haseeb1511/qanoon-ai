import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

import './ChatWindow.css';


const API_URL = import.meta.env.VITE_API_URL;

const ChatWindow = ({
    activeThread,
    messages,
    onUpdateMessages, // callback to update messages in parent
    file
}) => {
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false); //  Move loading state here
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);
    const abortControllerRef = useRef(null);

    /* ------------------ Scroll ------------------ */
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };
    useEffect(() => scrollToBottom(), [messages, loading]);

    /* ------------------ Auto-resize textarea ------------------ */
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
        }
    }, [input]);

    /* ------------------ Send Message ------------------ */
    const handleSubmit = async (e) => {
        e?.preventDefault();
        if (!input.trim() || loading) return;

        const message = input.trim();
        setInput("");
        setLoading(true);
        abortControllerRef.current = new AbortController();

        // Calculate the bot message index BEFORE adding messages
        const botMessageIndex = messages.length + 1;

        // Add user message and empty bot message together
        const newMessages = [
            ...messages,
            { role: 'human', content: message },
            { role: 'ai', content: '' }
        ];
        onUpdateMessages(newMessages);

        try {
            const url = activeThread
                ? `${API_URL}/follow_up`
                : `${API_URL}/ask`;

            const formData = new FormData();
            if (!activeThread) {
                formData.append('pdf', file);
            } else {
                formData.append('doc_id', activeThread.doc_id);
                formData.append('thread_id', activeThread.thread_id);
            }
            formData.append('question', message);

            const response = await fetch(url, {
                method: 'POST',
                body: formData,
                signal: abortControllerRef.current.signal,
            });

            if (!response.ok) throw new Error(`HTTP error: ${response.status}`);
            if (!response.body) throw new Error('No response body');

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';
            let botMessage = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || '';

                    for (const line of lines) {
                        const trimmedLine = line.trim();
                        if (!trimmedLine.startsWith('data:')) continue;

                        try {
                            // Parse the JSON first
                            const data = JSON.parse(trimmedLine.replace(/^data:\s*/, ''));

                            // ✅ Check for 'done' after parsing
                            if (data.type === 'done') {
                                console.log("Streaming finished");
                                setLoading(false); // stop loader
                                break; // exit loop since streaming is complete
                            }

                            if (data.token) {
                                botMessage += data.token;
                                onUpdateMessages(prev => {
                                    const updated = [...prev];
                                    updated[botMessageIndex] = { role: 'ai', content: botMessage };
                                    return updated;
                                });
                            } else if (data.type === 'error') {
                                onUpdateMessages(prev => {
                                    const updated = [...prev];
                                    updated[botMessageIndex] = { role: 'ai', content: `Error: ${data.message}` };
                                    return updated;
                                });
                            }
                        } catch (err) {
                            console.error('Failed to parse SSE:', err);
                        }
                    }

            }

            if (!botMessage) {
                onUpdateMessages(prev => {
                    const updated = [...prev];
                    updated[botMessageIndex] = { role: 'ai', content: "No response received. Please try again." };
                    return updated;
                });
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error('Chat error:', err);
                onUpdateMessages(prev => {
                    const updated = [...prev];
                    if (updated[botMessageIndex]) {
                        updated[botMessageIndex] = { role: 'ai', content: 'Something went wrong. Please try again.' };
                    } else {
                        updated.push({ role: 'ai', content: 'Something went wrong. Please try again.' });
                    }
                    return updated;
                });
            }
        } finally {
            setLoading(false);
            abortControllerRef.current = null;
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <div className="chat-container">
            <div className="chat-main custom-scrollbar">
                <div className="chat-inner">
                    {messages.length === 0 ? (
                    <div className="empty-state">
                        <h1>How can I help you?</h1>
                        <p>{file ? `"${file.name}" is ready. Ask me anything.` : "Upload a document to get started."}</p>
                    </div>

                    ) : (

                        // Typing Indicator 
                        <div className="flex flex-col">
                            {messages.map((msg, idx) => (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className={`message-bubble ${msg.role === 'human' ? 'user' : 'ai'}`}
                                >
                            {msg.content ? (
                                <div className="message-content">
                                    {msg.content}
                                </div>
                            ) : msg.role === 'ai' && idx === messages.length - 1 && loading ? (
                                <div className="typing-indicator">
                                    <span className="typing-dot"></span>
                                    <span className="typing-dot"></span>
                                    <span className="typing-dot"></span>
                                </div>
                    ) : null}

                                </motion.div>
                            ))}
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
                        placeholder="Type your question..."
                        rows={1}
                        disabled={loading || (!activeThread && !file)}
                        className="chat-textarea"
                    />
                    <button
                        onClick={handleSubmit}
                        disabled={loading || !input.trim() || (!activeThread && !file)}
                        className="send-btn"
                    >
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                </div>
                <p className="text-center text-[10px] text-[#676767] mt-3">
                    QanoonAI by Haseeb Manzoor
                </p>
            </div>
        </div>
    );
};

export default ChatWindow;