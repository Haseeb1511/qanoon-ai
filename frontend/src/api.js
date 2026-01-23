
import axios from "axios";

const API_BASE_URL = "http://127.0.0.1:8000";

export const api = {
  // Upload PDF and ask initial question
  askQuestion: async (pdfFile, question) => {
    const formData = new FormData();
    formData.append("pdf", pdfFile);
    formData.append("question", question);
    
    const response = await axios.post(`${API_BASE_URL}/ask`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  // Ask follow-up question
  followUp: async (docId, threadId, question) => {
    const formData = new FormData();
    formData.append("doc_id", docId);
    formData.append("thread_id", threadId);
    formData.append("question", question);

    const response = await axios.post(`${API_BASE_URL}/follow_up`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return response.data;
  },

  // Get all threads for sidebar
  getAllThreads: async () => {
    const response = await axios.get(`${API_BASE_URL}/all_threads`);
    return response.data;
  },

  // Get specific thread details
  getThread: async (threadId) => {
    const response = await axios.get(`${API_BASE_URL}/get_threads/${threadId}`);
    return response.data;
  }
};
