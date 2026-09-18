import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthApi } from "../api";
import { useAuth } from "../auth";

export function ChangePasswordPage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    try {
      await AuthApi.changePassword(currentPassword, newPassword);
      const me = await AuthApi.me();
      setUser(me);
      navigate(me.app_role === "ADMIN" ? "/admin" : "/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process request");
    }
  }

  const renderEyeIcon = (show: boolean) => (
    show ? (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
        <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
        <path d="M14.12 14.12a3 3 0 1 1-4.24-4.24" />
        <line x1="1" y1="1" x2="23" y2="23" />
      </svg>
    ) : (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    )
  );

  return (
    <main className="auth-shell">
      <form className="card" onSubmit={onSubmit}>
        <h1>Change password</h1>
        <p className="muted">Hello {user?.full_name}. Choose a new password of at least 6 characters, including at least one letter and one number.</p>
        {error ? <p role="alert" className="error">{error}</p> : null}
        <label>
          Current password
          <div className="password-wrapper">
            <input 
              type={showCurrentPassword ? "text" : "password"} 
              value={currentPassword} 
              onChange={(e) => setCurrentPassword(e.target.value)} 
              required 
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowCurrentPassword(!showCurrentPassword)}
              aria-label={showCurrentPassword ? "Hide password" : "Show password"}
              tabIndex={-1}
            >
              {renderEyeIcon(showCurrentPassword)}
            </button>
          </div>
        </label>
        <label>
          New password
          <div className="password-wrapper">
            <input 
              type={showNewPassword ? "text" : "password"} 
              value={newPassword} 
              onChange={(e) => setNewPassword(e.target.value)} 
              required 
              minLength={6} 
              pattern="(?=.*[A-Za-z])(?=.*\d).+" 
              title="Password must be at least 6 characters and contain at least one letter and one number" 
            />
            <button
              type="button"
              className="password-toggle"
              onClick={() => setShowNewPassword(!showNewPassword)}
              aria-label={showNewPassword ? "Hide password" : "Show password"}
              tabIndex={-1}
            >
              {renderEyeIcon(showNewPassword)}
            </button>
          </div>
        </label>
        <button type="submit">Update password</button>
      </form>
    </main>
  );
}

