import React, { useState, useRef, useEffect } from "react";
import { Send, Loader2, Mic } from "lucide-react";
import { motion } from "framer-motion";

import "./ChatWindow.css";
import { supabase } from "../../supabaseClient";

const API_URL = import.meta.env.VITE_BACKEND_URL;

const ChatWindow = ({
  activeThread,
  messages,
  onUpdateMessages,      // callback from parent to update messages
  file,
  onNewThreadCreated     // callback when a new thread is created
}) => {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const abortControllerRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  // ========================= Auto-scroll messages =========================
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // ========================= Auto-adjust textarea height ==================
  useEffect(() => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = "auto";
    textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
  }, [input]);

  // ========================= Helper: Stream AI response =================
  const handleStreamResponse = async (response, botMessageIndex) => {
    if (!response.body) return setLoading(false);

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");

    let buffer = "";
    let botMessage = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const data = JSON.parse(line.replace(/^data:\s*/, ""));

        // Stream AI tokens
        if (data.token) {
          botMessage += data.token;
          onUpdateMessages((prev) => {
            const updated = [...prev];
            updated[botMessageIndex] = { role: "ai", content: botMessage };
            return updated;
          });
        }

        // Done event
        if (data.type === "done") {
          setLoading(false);
          return;
        }

        // Thread creation event
        if (data.type === "thread_created") {
          onNewThreadCreated?.(data.thread_id);
        }
      }
    }
  };

  // ========================= Submit text question =======================
  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput("");
    setLoading(true);
    abortControllerRef.current = new AbortController();

    const botMessageIndex = messages.length + 1;

    // Add placeholders for human and AI messages
    onUpdateMessages([
      ...messages,
      { role: "human", content: userMessage },
      { role: "ai", content: "" }
    ]);

    try {
      const {
        data: { session }
      } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) throw new Error("No auth token");

      const isNewThread = !activeThread;
      const url = isNewThread ? `${API_URL}/ask` : `${API_URL}/follow_up`;

      const formData = new FormData();
      if (isNewThread) formData.append("pdf", file);
      else formData.append("thread_id", activeThread.thread_id);

      formData.append("question", userMessage);

      const response = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
        signal: abortControllerRef.current.signal
      });

      await handleStreamResponse(response, botMessageIndex);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  // ========================= Voice question: send audio =================
  const sendAudio = async () => {
    setLoading(true);
    const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("audio", audioBlob, "voice.webm");

    const isNewThread = !activeThread;
    if (isNewThread) formData.append("pdf", file);
    else formData.append("thread_id", activeThread.thread_id);

    abortControllerRef.current = new AbortController();

    try {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) throw new Error("No auth token");

      const url = isNewThread ? `${API_URL}/ask/audio` : `${API_URL}/follow_up/audio`;

      const response = await fetch(url, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
        signal: abortControllerRef.current.signal,
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      let botMessage = "";
      let botMessageIndex = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;

          let data;
          try {
            data = JSON.parse(line.replace(/^data:\s*/, ""));
          } catch (err) {
            console.error("SSE parse error:", line, err);
            continue;
          }

          // Append transcribed user message
          if (data.transcribed_text) {
            onUpdateMessages((prev) => {
              botMessageIndex = prev.length + 1; // next message will be bot
              return [...prev, { role: "human", content: data.transcribed_text }, { role: "ai", content: "" }];
            });
          }

          // Stream AI tokens
          if (data.token) {
            botMessage += data.token;
            onUpdateMessages((prev) => {
              if (botMessageIndex === null) botMessageIndex = prev.length - 1;
              const updated = [...prev];
              updated[botMessageIndex] = { role: "ai", content: botMessage };
              return updated;
            });
          }

          // Done
          if (data.type === "done") setLoading(false);

          // New thread
          if (data.type === "thread_created") onNewThreadCreated?.(data.thread_id);
        }
      }
    } catch (err) {
      console.error(err);
      setLoading(false);
    } finally {
      setRecording(false);
      abortControllerRef.current = null;
    }
  };

  // ============================== Audio Recording =======================
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        audioChunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = sendAudio;
      mediaRecorderRef.current.start();
      setRecording(true);
    } catch (err) {
      console.error("Microphone error:", err);
      alert("Microphone access denied");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && recording) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((track) => track.stop());
      setRecording(false);
    }
  };


  // ========================= Waveform animation =========================
// Simple visual indicator so user KNOWS recording is active
const Waveform = () => {
  return (
    <div className="waveform">
      <span />
      <span />
      <span />
      <span />
    </div>
  );
};


  // ========================= Render Chat ================================
  return (
    <div className="chat-container">
      <div className="chat-main">
        {messages.map((msg, idx) => (
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`message-bubble ${msg.role === "human" ? "user" : "ai"}`}
          >
            <div className="message-content">
              {msg.content || (loading && idx === messages.length - 1 && (
                <div className="typing-indicator">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              ))}
            </div>
          </motion.div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="input-area">
        <div className="input-wrapper">
          <textarea
            className="chat-textarea"
            ref={textareaRef}
            value={input}
            placeholder="Type your question..."
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            disabled={loading || (!activeThread && !file)}
          />

           <div className="actions">
          {/* Send button */}
          <button
            className="send-btn"
            onClick={handleSubmit}
            disabled={loading || !input.trim()}
          >
            {loading ? <Loader2 className="animate-spin" /> : <Send />}
          </button>

          {/* Audio record button
              - Shows Mic when idle
              - Shows animated waveform when recording
          */}
          <button
            className={`mic-btn ${recording ? "recording" : ""}`}
            onClick={recording ? stopRecording : startRecording}
            disabled={loading}
          >
            {recording ? <Waveform /> : <Mic />}
          </button>
        </div>


          </div>
        </div>
      </div>
  );
};

export default ChatWindow;