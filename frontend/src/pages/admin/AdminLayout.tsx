import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { AuthApi } from "../../api";
import { useAuth } from "../../auth";
import { AdminBadge } from "../../components/AdminBadge";

export function AdminLayout() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  async function logout() {
    await AuthApi.logout();
    setUser(null);
    navigate("/admin/login");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand" style={{ fontFamily: "'Outfit', 'Inter', sans-serif", fontSize: "1.2rem", fontWeight: 700, background: "linear-gradient(90deg, #60a5fa, #a78bfa)", WebkitBackgroundClip: "text", color: "transparent" }}>
          {user?.company_name || "ACME Corp"}
        </div>
        <div className="identity">
          <div className="user-identity-wrap">
            <span style={{ fontWeight: 600 }}>{user?.full_name}</span>
            {user?.app_role === "ADMIN" && <AdminBadge />}
          </div>
          <span className="muted">{user?.email}</span>
          <button className="linkish" onClick={() => void logout()}>
            Logout
          </button>
        </div>
      </header>
      <div className="admin-layout">
        <nav className="sidebar" aria-label="Admin">
          <NavLink to="/admin" end>
            Dashboard
          </NavLink>
          <NavLink to="/admin/users">Users</NavLink>
          <NavLink to="/admin/documents">Documents</NavLink>
          <NavLink to="/admin/audit">Audit logs</NavLink>
        </nav>
        <section className="admin-main">
          <Outlet />
        </section>
      </div>
    </div>
  );
}
