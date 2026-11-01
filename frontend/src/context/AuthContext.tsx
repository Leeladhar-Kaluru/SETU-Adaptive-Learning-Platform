import React, { createContext, useCallback, useContext, useEffect, useRef, useState, ReactNode } from 'react';
import { ApiError, api, UserProfileData } from '../services/api';
import { clearOfflineData } from '../db/indexedDB';
import { clearActiveUserId, getActiveUserId, setActiveUserId } from '../services/session';

interface AuthContextType {
  user: UserProfileData | null;
  token: string | null;
  isLoading: boolean;
  sessionError: string | null;
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
  }) => Promise<UserProfileData>;
  logout: () => Promise<void>;
  retrySession: () => Promise<void>;
  updateProfile: (updates: Partial<UserProfileData>) => Promise<void>;
  openTour: () => void;
  closeTour: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfileData | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('setu_auth_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [isTourOpen, setIsTourOpen] = useState<boolean>(false);
  const loadInFlight = useRef<Promise<void> | null>(null);

  const loadUser = useCallback(async () => {
    if (loadInFlight.current) return loadInFlight.current;

    const run = (async () => {
      const storedToken = localStorage.getItem('setu_auth_token');
      if (!storedToken) {
        setToken(null);
        setUser(null);
        setSessionError(null);
        setIsLoading(false);
        return;
      }

      setToken(storedToken);
      setIsLoading(true);
      setSessionError(null);

      for (let attempt = 0; attempt < 3; attempt += 1) {
        try {
          const profile = await api.getProfile();
          const active = getActiveUserId();
          if (active && active !== profile.id) {
            await clearOfflineData();
          }
          setActiveUserId(profile.id);
          setUser(profile);
          setSessionError(null);
          if (!profile.tourCompleted && !profile.onboardingCompleted) {
            setIsTourOpen(true);
          }
          setIsLoading(false);
          return;
        } catch (err) {
          const rejected = err instanceof ApiError && (err.status === 401 || err.status === 403);
          if (rejected) {
            localStorage.removeItem('setu_auth_token');
            setToken(null);
            setUser(null);
            setSessionError(null);
            setIsLoading(false);
            return;
          }
          if (attempt < 2) {
            await new Promise((resolve) => window.setTimeout(resolve, 400 * (attempt + 1)));
          }
        }
      }

      console.warn('SETU could not refresh the saved session after retries.');
      setUser(null);
      setSessionError('SETU could not reach your desk. Your session is still saved.');
      setIsLoading(false);
    })();

    loadInFlight.current = run;
    try {
      await run;
    } finally {
      loadInFlight.current = null;
    }
  }, []);

  useEffect(() => {
    void loadUser();
  }, [loadUser]);

  const applySession = async (accessToken: string, profile: UserProfileData) => {
    const previous = getActiveUserId();
    if (previous && previous !== profile.id) {
      await clearOfflineData();
    }
    localStorage.setItem('setu_auth_token', accessToken);
    setActiveUserId(profile.id);
    setToken(accessToken);
    setUser(profile);
    setSessionError(null);
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
    return res.user;
  };

  const logout = async () => {
    await clearOfflineData();
    localStorage.removeItem('setu_auth_token');
    clearActiveUserId();
    setToken(null);
    setUser(null);
    setSessionError(null);
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
        sessionError,
        isTourOpen,
        login,
        signup,
        logout,
        retrySession: loadUser,
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

