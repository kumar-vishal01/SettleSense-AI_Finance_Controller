import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { Session, User } from "@supabase/supabase-js";

import { supabase } from "../lib/supabase";

interface AuthContextValue {
  user: User | null;
  session: Session | null;
  loading: boolean;

  signIn: (
    email: string,
    password: string,
  ) => Promise<void>;

  signUp: (
    email: string,
    password: string,
    fullName?: string,
  ) => Promise<void>;

  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({
  children,
}: AuthProviderProps) {
  const [session, setSession] =
    useState<Session | null>(null);

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const initializeAuth = async () => {
      const {
        data: { session },
        error,
      } = await supabase.auth.getSession();

      if (!mounted) {
        return;
      }

      if (error) {
        console.error(
          "Failed to load Supabase session:",
          error,
        );

        setSession(null);
      } else {
        setSession(session);
      }

      setLoading(false);
    };

    initializeAuth();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        if (!mounted) {
          return;
        }

        setSession(session);
        setLoading(false);
      },
    );

    return () => {
      mounted = false;
      subscription.unsubscribe();
    };
  }, []);

  /**
   * Sign in existing user
   */
  const signIn = async (
    email: string,
    password: string,
  ) => {
    const { error } =
      await supabase.auth.signInWithPassword({
        email,
        password,
      });

    if (error) {
      throw error;
    }
  };

  /**
   * Create new user
   */
  const signUp = async (
    email: string,
    password: string,
    fullName?: string,
  ) => {
    const { error } =
      await supabase.auth.signUp({
        email,
        password,
        options: {
          data: {
            full_name: fullName ?? "",
          },
        },
      });

    if (error) {
      throw error;
    }
  };

  /**
   * Sign out current user
   */
  const signOut = async () => {
    const { error } =
      await supabase.auth.signOut();

    if (error) {
      throw error;
    }
  };

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      session,
      loading,
      signIn,
      signUp,
      signOut,
    }),
    [session, loading],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside an AuthProvider",
    );
  }

  return context;
}