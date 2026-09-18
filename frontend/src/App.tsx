import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthApi, type User } from "./api";
import { ErrorBoundary } from "./ErrorBoundary";
import { AuthContext } from "./auth";
import { AdminLayout } from "./pages/admin/AdminLayout";
import { AuditPage } from "./pages/admin/AuditPage";
import { DashboardPage } from "./pages/admin/DashboardPage";
import { DocumentsPage } from "./pages/admin/DocumentsPage";
import { UsersPage } from "./pages/admin/UsersPage";
import { ChangePasswordPage } from "./pages/ChangePasswordPage";
import { ChatPage } from "./pages/ChatPage";
import { LoginPage } from "./pages/LoginPage";

function Guard({
  user,
  loading,
  role,
  children,
}: {
  user: User | null;
  loading: boolean;
  role?: "ADMIN" | "EMPLOYEE";
  children: ReactNode;
}) {
  if (loading) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to={role === "ADMIN" ? "/admin/login" : "/login"} replace />;
  if (user.must_change_password) return <Navigate to="/change-password" replace />;
  if (role && user.app_role !== role) return <Navigate to={user.app_role === "ADMIN" ? "/admin" : "/app"} replace />;
  return <>{children}</>;
}

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    AuthApi.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AuthContext.Provider value={{ user, setUser, loading }}>
      <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<LoginPage initialPortal="employee" />} />
        <Route path="/admin/login" element={<LoginPage initialPortal="admin" />} />

        <Route
          path="/change-password"
          element={loading ? <p>Loading…</p> : user ? <ChangePasswordPage /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/app"
          element={
            <Guard user={user} loading={loading} role="EMPLOYEE">
              <ChatPage />
            </Guard>
          }
        />
        <Route
          path="/admin"
          element={
            <Guard user={user} loading={loading} role="ADMIN">
              <AdminLayout />
            </Guard>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="users" element={<UsersPage />} />
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
        <Route path="/" element={<Navigate to="/login" replace />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
      </ErrorBoundary>
    </AuthContext.Provider>
  );
}
