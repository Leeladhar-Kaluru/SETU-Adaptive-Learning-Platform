import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api, UserProfileData } from '../services/api';
import { clearOfflineData } from '../db/indexedDB';
import { clearActiveUserId, getActiveUserId, setActiveUserId } from '../services/session';

interface AuthContextType {
  user: UserProfileData | null;
  token: string | null;
  isLoading: boolean;
  isTourOpen: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (params: {
    email: string;
    password: string;
    displayName: string;
    role?: 'student' | 'teacher';
    grade?: number;
    boardId?: string;
    preferredLanguage?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  updateProfile: (updates: Partial<UserProfileData>) => Promise<void>;
  openTour: () => void;
  closeTour: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfileData | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('setu_auth_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isTourOpen, setIsTourOpen] = useState<boolean>(false);

  useEffect(() => {
    async function loadUser() {
      const storedToken = localStorage.getItem('setu_auth_token');
      if (!storedToken) {
        setIsLoading(false);
        return;
      }
      try {
        const profile = await api.getProfile();
        const active = getActiveUserId();
        if (active && active !== profile.id) {
          await clearOfflineData();
        }
        setActiveUserId(profile.id);
        setUser(profile);
        if (!profile.tourCompleted && !profile.onboardingCompleted) {
          setIsTourOpen(true);
        }
      } catch (err) {
        console.warn('Session expired or profile failed to load:', err);
        localStorage.removeItem('setu_auth_token');
        setToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    loadUser();
  }, []);

  const applySession = async (accessToken: string, profile: UserProfileData) => {
    const previous = getActiveUserId();
    if (previous && previous !== profile.id) {
      await clearOfflineData();
    }
    localStorage.setItem('setu_auth_token', accessToken);
    setActiveUserId(profile.id);
    setToken(accessToken);
    setUser(profile);
  };

  const login = async (email: string, password: string) => {
    const res = await api.login({ email, password });
    await applySession(res.accessToken, res.user);
    if (!res.user.onboardingCompleted) {
      setIsTourOpen(true);
    }
  };

  const signup = async (params: {
    email: string;
    password: string;
    displayName: string;
    role?: 'student' | 'teacher';
    grade?: number;
    boardId?: string;
    preferredLanguage?: string;
  }) => {
    const res = await api.signup(params);
    await applySession(res.accessToken, res.user);
    setIsTourOpen(true);
  };

  const logout = async () => {
    await clearOfflineData();
    localStorage.removeItem('setu_auth_token');
    clearActiveUserId();
    setToken(null);
    setUser(null);
  };

  const updateProfile = async (updates: Partial<UserProfileData>) => {
    const res = await api.updateProfile(updates);
    setUser(res.profile);
  };

  const openTour = () => setIsTourOpen(true);
  const closeTour = () => setIsTourOpen(false);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isTourOpen,
        login,
        signup,
        logout,
        updateProfile,
        openTour,
        closeTour
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

