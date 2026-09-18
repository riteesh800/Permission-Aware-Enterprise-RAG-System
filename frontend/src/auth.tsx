import { createContext, useContext } from "react";
import type { User } from "./api";

export type AuthState = {
  user: User | null;
  setUser: (user: User | null) => void;
  loading: boolean;
};

export const AuthContext = createContext<AuthState>({
  user: null,
  setUser: () => undefined,
  loading: true,
});

export function useAuth() {
  return useContext(AuthContext);
}
