import { createContext, useContext, useEffect, useState } from 'react';
import { apiClient } from '@/lib/api-client';

interface User {
  id: string;
  email: string;
  spotify_connected?: boolean;
}

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const restoreSession = async () => {
      const token = apiClient.getToken();
      if (token) {
        try {
          const userData = await apiClient.getCurrentUser();
          setUser(userData);
        } catch {
          // Token invalid or expired — clear it
          apiClient.setToken(null);
        }
      }
      setLoading(false);
    };
    restoreSession();
  }, []);

  const signIn = async (email: string, password: string) => {
    try {
      const response = await apiClient.login(email, password);
      setUser(response.user);
    } catch (error) {
      throw error;
    }
  };

  const signUp = async (email: string, password: string) => {
    try {
      const response = await apiClient.register(email, password);
      setUser(response.user);
    } catch (error) {
      throw error;
    }
  };

  const signOut = async () => {
    try {
      await apiClient.logout();
    } finally {
      setUser(null);
    }
  };

  const refreshUser = async () => {
    try {
      const userData = await apiClient.getCurrentUser();
      setUser(userData);
    } catch {
      // ignore
    }
  };

  // Check for ?spotify=connected in URL after OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('spotify') === 'connected') {
      refreshUser();
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
