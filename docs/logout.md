import { MessageSquare, Plus, Upload, X, File, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../../supabaseClient';


# Logout handler function added:
```jsx
const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/login');
};
```


# Logout button :
```jsx
<button onClick={handleLogout} className="logout-btn">
    <LogOut className="w-4 h-4" />
    <span>Sign Out</span>
</button>
```


```css
.logout-btn {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px;
    margin-top: 12px;
    border-radius: 8px;
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 500;
    transition: all 0.2s;
    cursor: pointer;
    border: 1px solid transparent;
    background: transparent;
}

.logout-btn:hover {
    background-color: rgba(239, 68, 68, 0.1);
    color: #ef4444;
    border-color: rgba(239, 68, 68, 0.3);
}

```