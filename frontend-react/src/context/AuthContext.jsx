import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('tc_user');
    return stored ? JSON.parse(stored) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('tc_token');
    if (token) {
      authAPI.me()
        .then(r => {
          setUser(r.data);
          localStorage.setItem('tc_user', JSON.stringify(r.data));
        })
        .catch(() => {
          localStorage.removeItem('tc_token');
          localStorage.removeItem('tc_user');
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email, password) => {
    const r = await authAPI.login(email, password);
    const token = r.data.access_token;
    localStorage.setItem('tc_token', token);
    const me = await authAPI.me();
    setUser(me.data);
    localStorage.setItem('tc_user', JSON.stringify(me.data));
    return me.data;
  };

  const logout = () => {
    localStorage.removeItem('tc_token');
    localStorage.removeItem('tc_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
