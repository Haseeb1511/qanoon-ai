// api.js
// This file contains all API calls to our backend server
// It uses axios for HTTP requests and automatically adds your Supabase auth token

import axios from "axios";

// -------------------------
// 1️⃣ Base URL of the API
// -------------------------
// This URL is set in your .env file (VITE_BACKEND_URL)
// Example: VITE_BACKEND_URL=http://localhost:8000
const API_BASE_URL = import.meta.env.VITE_BACKEND_URL;

// -------------------------
// 2️⃣ Create an Axios instance
// -------------------------
// Axios instance allows us to set default configuration for all requests
const axiosInstance = axios.create({
  baseURL: API_BASE_URL, // all requests will start with this URL
});

// -------------------------
// 3️⃣ Add interceptor to attach auth token automatically
// -------------------------
// Interceptors allow us to run code before every request
axiosInstance.interceptors.request.use(
  async (config) => {
    // Import Supabase client dynamically
    const { supabase } = await import('../supabaseClient');

    // Get current session
    const { data: { session } } = await supabase.auth.getSession();

    // If user is logged in, add the access token to request headers
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }

    return config; // continue with the request
  },
  (error) => Promise.reject(error) // handle errors
);

// -------------------------
// 4️⃣ API functions
// -------------------------
export const api = {
  // 🔹 Get all threads for the sidebar
  getAllThreads: async () => {
    const response = await axiosInstance.get('/all_threads');
    return response.data; // return only the data part
  },

  // 🔹 Get specific thread details including messages
  getThread: async (threadId) => {
    const response = await axiosInstance.get(`/get_threads/${threadId}`);
    return response.data;
  },

  // 🔹 Get TOTAL token usage for the current user across ALL threads
  getUserTotalTokenUsage: async () => {
    const response = await axiosInstance.get('/user/tokens');
    return response.data;
  },

  // 🔹 Get user settings (email, custom prompt)
  getSettings: async () => {
    const response = await axiosInstance.get('/settings');
    return response.data;
  },

  // 🔹 Save custom prompt
  savePrompt: async (customPrompt) => {
    const response = await axiosInstance.post('/settings/prompt', {
      custom_prompt: customPrompt
    });
    return response.data;
  },

  // 🔹 Reset prompt to default
  resetPrompt: async () => {
    const response = await axiosInstance.delete('/settings/prompt');
    return response.data;
  },
};
