
## 1️⃣What Google + Supabase Auth does for you:

Google OAuth is an external login provider.
When you click “Login with Google”, the user is redirected to Google.
Google asks them for email/password on their site, not on your app.
After they log in on Google, Supabase gets a token and your app now knows who the user is.
✅ This means you don’t need a login form for email/password if you only use Google login.



## **1️⃣ Install Required Packages**

You’ll need a few packages for Supabase auth integration:

```bash
pip install supabase pyjwt python-dotenv fastapi[all] httpx
```

* `supabase` → Supabase Python client
* `pyjwt` → To decode JWT from Supabase
* `httpx` → For async HTTP requests (needed by FastAPI for auth)
* `python-dotenv` → For loading `.env`

---

## **2️⃣ Configure Environment Variables**

Create or update your `.env` (make sure Docker passes it with `--env-file .env`):

```env
SUPABASE_URL=https://xyzcompany.supabase.co
SUPABASE_KEY=your-service-role-key-or-anon-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

---

## **3️⃣ Initialize Supabase Client**

You already have `src/db_connection/connection.py`. Add auth support:

```python
from supabase import create_client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)
```

✅ This will allow you to access both database and auth API.

---




## **5️⃣ Add Authentication Middleware / Dependency**

Create a file `backend/dependencies/auth.py`:

```python
from fastapi import Request, HTTPException
from src.db_connection.connection import supabase_client
import jwt

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing auth")

    token = auth_header.replace("Bearer ", "")

    user = supabase_client.auth.get_user(token)

    if not user or not user.user:
        raise HTTPException(status_code=401, detail="Invalid token")

    return user.user
```

# FrontEnd
first install this for supbase login UI
``npm install @supabase/auth-ui-react @supabase/auth-ui-shared``

### app.jsx
**Session check on page load - redirects to /login if no session:**
```js
const { data: { session } } = await supabase.auth.getSession();
if (!session?.access_token) navigate("/login");

```

### api.js
**Auth token interceptor - automatically attaches JWT to every API request:**
```js
const { data: { session } } = await supabase.auth.getSession();
config.headers.Authorization = `Bearer ${session.access_token}`;

```

### superbaseClient.js
**Creates the Supabase client instance used for all auth operations:**
```js
import { createClient } from "@supabase/supabase-js";

// -------------------- Supabase config --------------------
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

// -------------------- Create client --------------------
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

```

### Login
```js

import React from "react";
import "./Login.css";
import { supabase } from "../../supabaseClient";

const FRONTEND_URL = import.meta.env.VITE_FRONTEND_URL;

export default function Login() {
  const handleLogin = async () => {
    try {
      await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: FRONTEND_URL,
        },
      });
    } catch (error) {
      console.error("Login failed:", error.message);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <h1 className="login-title">QanoonAI</h1>
        <p className="login-subtitle">Your AI Legal Assistant</p>

        <button onClick={handleLogin} className="google-login-btn">
          <svg className="google-icon" viewBox="0 0 24 24" width="20" height="20">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Continue with Google
        </button>
      </div>
    </div>
  );
}

```

### login.css
```css
.login-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #0f0f0f 0%, #1a1a2e 50%, #16213e 100%);
}

.login-card {
  background: rgba(30, 30, 40, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  padding: 3rem 2.5rem;
  text-align: center;
  box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(10px);
  max-width: 400px;
  width: 90%;
}

.login-title {
  font-size: 2.5rem;
  font-weight: 700;
  color: #fff;
  margin-bottom: 0.5rem;
  letter-spacing: -0.5px;
}

.login-subtitle {
  color: #888;
  font-size: 1rem;
  margin-bottom: 2rem;
}

.google-login-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  width: 100%;
  background: #fff;
  color: #333;
  font-size: 1rem;
  font-weight: 500;
  padding: 14px 24px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.google-login-btn:hover {
  background: #f5f5f5;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.google-login-btn:active {
  transform: translateY(0);
}

.google-icon {
  flex-shrink: 0;
}

```

### Logout

```js
    // ----------------- Logout Handler -----------------
    const handleLogout = async () => {
        await supabase.auth.signOut();
        navigate('/login');
    };



   <div className="sidebar-footer-buttons">
      <button onClick={handleLogout} className="logout-btn">
         <LogOut className="w-4 h-4" />
         <span>Sign Out</span>
      </button>
   </div>

```



---

## **6️⃣ Protect Routes with Dependency**

In your `chat.py` or `threads.py`, you can now require authentication:
using user_id

---


---






---

## **2️⃣ JWT (JSON Web Token) — Authentication**

* **What it is:** A **token format** used to **prove identity**. Contains claims like `sub` (user ID), `email`, etc.
* **In your case:**

  * Supabase issues a **JWT access token** after the Google OAuth flow.
  * Your FastAPI backend decodes the JWT to verify who the user is (`get_current_user` dependency).
  * Routes use this decoded JWT to **authorize access** (e.g., only show threads for `user_id` from JWT).

✅ This part is **JWT-based authentication / authorization**.

---

## **3️⃣ How they work together in your app**

1. **OAuth 2.0** → Used **once** to let the user log in with Google.
2. **JWT** → Used **for every API request** to verify the user’s identity.

So technically:

* **OAuth 2.0** handles the login process with Google.
* **JWT** handles authentication inside your backend once the user is logged in.

---


---

## **1️⃣ GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET**

These come from **Google Cloud Console** because Google is your OAuth provider.

### Steps to get them:

1. Go to [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials)
2. Create a **new project** (or use an existing one).
3. **Enable OAuth consent screen** for your project:

   * Go to `APIs & Services → OAuth consent screen`.
   * Choose `External` if your app will be used by anyone with a Google account.
   * Fill in the required fields (app name, email, etc.).
4. Go to `Credentials → Create Credentials → OAuth client ID`.

   * Application type: **Web application**.
   * Authorized redirect URIs:

     ```
     http://localhost:8000/auth/callback
     ```

     (or your production URL when deployed)
5. After creating, Google will give you:

   * **Client ID** → use for `GOOGLE_CLIENT_ID`
   * **Client Secret** → use for `GOOGLE_CLIENT_SECRET`

✅ That’s it. These two are what Supabase needs to allow Google login.

---



## ✅ Correct Place to Enable Google (New Supabase UI)

### 🔹 Step-by-step (Exact clicks)

1. Open **Supabase Dashboard**
2. Select your project
3. Left sidebar → **Authentication**
4. Click **Providers** (NOT “Sign-in methods”)
5. Scroll down → **OAuth Providers**
6. You will see:

   * Google
   * GitHub
   * Discord
   * etc.

👉 **Google is there**, just lower on the page.

---


---

## ✅ What to Do Once You Find Google

### Enable Google

* Toggle **Enable**
* Paste:

  * **Client ID**
  * **Client Secret**
* Save

---

# Copy the call back url and paste it in google cloud console
![alt text](image-3.png)


## ✅ VERY IMPORTANT: Redirect URLs (People Miss This)
Still inside **Authentication**:
### Go to → **URL Configuration**
Set:

**Site URL**

```
http://localhost:5173
```

**Additional Redirect URLs**

```
http://localhost:8000/auth/callback
```

![alt text](image-4.png)
Save.

---

## ✅ How to Verify It Worked (Before Coding)

Paste this in browser:

```
https://YOUR_PROJECT_ID.supabase.co/auth/v1/authorize?provider=google
```

If you see:

* Google account picker → ✅ working
* Error page → ❌ misconfigured

---

# we can view out authenticated user here
go to Authentication --> users
![alt text](image.png)