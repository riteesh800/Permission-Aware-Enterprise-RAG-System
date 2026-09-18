import { FormEvent, useEffect, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AuthApi } from "../api";
import { useAuth } from "../auth";

type Props = { initialPortal?: "admin" | "employee" };

function Accordion({ title, children }: { title: string, children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="accordion">
      <button type="button" className={`accordion-header ${open ? "open" : ""}`} onClick={() => setOpen(!open)}>
        {title}
        <span className="accordion-arrow">▼</span>
      </button>
      <div className={`accordion-content ${open ? "open" : ""}`}>
        {children}
      </div>
    </div>
  );
}

export function LoginPage({ initialPortal = "employee" }: Props) {
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Portal selection: employee or admin
  const queryPortal = searchParams.get("portal");
  const [portal, setPortal] = useState<"admin" | "employee">(
    queryPortal === "admin" || initialPortal === "admin" ? "admin" : "employee"
  );
  
  // Toggle between landing info and auth form
  const [showForms, setShowForms] = useState(false);

  // Admin sub-mode: sign in, create account, or forgot password
  const [adminMode, setAdminMode] = useState<"login" | "register" | "forgot">("login");

  // Common Login fields
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const [regName, setRegName] = useState("");
  const [regCompany, setRegCompany] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirmPassword, setRegConfirmPassword] = useState("");
  const [showRegPassword, setShowRegPassword] = useState(false);

  // OTP Verification state
  const [otpStep, setOtpStep] = useState(false);
  const [forgotStep, setForgotStep] = useState<1 | 2 | 3>(1);
  const [otp, setOtp] = useState("");
  const [resendTimer, setResendTimer] = useState(0);

  // Feedback states
  const [error, setError] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Handle resend countdown timer
  useEffect(() => {
    if (resendTimer <= 0) return;
    const interval = setInterval(() => {
      setResendTimer((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [resendTimer]);

  function switchPortal(target: "admin" | "employee") {
    setPortal(target);
    setError(null);
    setInfoMsg(null);
    setIdentifier("");
    setPassword("");
    setCompanyName("");
  }

  function switchAdminMode(target: "login" | "register" | "forgot") {
    setAdminMode(target);
    setError(null);
    setInfoMsg(null);
    setOtpStep(false);
    setForgotStep(1);
    setOtp("");
  }

  // Handle standard Login (Employee or Admin)
  async function onLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setInfoMsg(null);

    try {
      const result = await AuthApi.login(
        identifier, 
        password, 
        portal === "employee" ? companyName : undefined
      );
      if (portal === "admin" && result.user.app_role !== "ADMIN") {
        await AuthApi.logout();
        setUser(null);
        setError("Invalid credentials for admin portal");
        return;
      }
      if (portal === "employee" && result.user.app_role !== "EMPLOYEE") {
        // Admin logging into employee portal gets redirected to admin
        setUser(result.user);
        navigate("/admin");
        return;
      }

      setUser(result.user);
      if (result.user.must_change_password) {
        navigate("/change-password");
        return;
      }
      navigate(portal === "admin" ? "/admin" : "/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid credentials");
    } finally {
      setBusy(false);
    }
  }

  // Step 1: Send OTP to Gmail
  async function onSendOtp(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setInfoMsg(null);

    if (regPassword.length < 6 || !/[a-zA-Z]/.test(regPassword) || !/\d/.test(regPassword)) {
      setError("Password must be at least 6 characters and contain at least one letter and one number");
      return;
    }

    if (regPassword !== regConfirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setBusy(true);
    try {
      const res = await AuthApi.sendAdminOtp(regEmail);
      setOtpStep(true);
      setResendTimer(60);
      setInfoMsg(res.message || `Verification code sent to ${regEmail}. Please check your inbox or spam folder.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send verification code");
    } finally {
      setBusy(false);
    }
  }

  // Resend OTP
  async function handleResendOtp() {
    if (resendTimer > 0 || busy) return;
    setBusy(true);
    setError(null);
    try {
      await AuthApi.sendAdminOtp(regEmail);
      setResendTimer(60);
      setInfoMsg(`A new verification code was sent to ${regEmail}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resend code");
    } finally {
      setBusy(false);
    }
  }

  // Step 2: Verify OTP and create Admin account
  async function onVerifyOtp(event: FormEvent) {
    event.preventDefault();
    if (otp.trim().length !== 6) {
      setError("Please enter the complete 6-digit verification code");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const result = await AuthApi.verifyAdminOtp({
        full_name: regName,
        company_name: regCompany,
        email: regEmail,
        password: regPassword,
        otp: otp.trim(),
      });
      setUser(result.user);
      navigate("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid or expired verification code");
    } finally {
      setBusy(false);
    }
  }

  // --- Forgot Password Flow ---
  async function onSendForgotOtp(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setInfoMsg(null);

    setBusy(true);
    try {
      const res = await AuthApi.sendAdminForgotPasswordOtp(regEmail);
      setForgotStep(2);
      setResendTimer(60);
      setInfoMsg(res.message || `Verification code sent to ${regEmail}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send reset code");
    } finally {
      setBusy(false);
    }
  }

  async function handleResendForgotOtp() {
    if (resendTimer > 0 || busy) return;
    setBusy(true);
    setError(null);
    try {
      await AuthApi.sendAdminForgotPasswordOtp(regEmail);
      setResendTimer(60);
      setInfoMsg(`A new reset code was sent to ${regEmail}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resend code");
    } finally {
      setBusy(false);
    }
  }

  async function onVerifyForgotOtp(event: FormEvent) {
    event.preventDefault();
    if (otp.trim().length !== 6) {
      setError("Please enter the complete 6-digit verification code");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await AuthApi.verifyAdminForgotPasswordOtp(regEmail, otp.trim());
      setForgotStep(3);
      setInfoMsg("Code verified! Please enter your new password.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid or expired code");
    } finally {
      setBusy(false);
    }
  }

  async function onResetPassword(event: FormEvent) {
    event.preventDefault();
    if (regPassword.length < 6 || !/[a-zA-Z]/.test(regPassword) || !/\d/.test(regPassword)) {
      setError("Password must be at least 6 characters and contain at least one letter and one number");
      return;
    }
    if (regPassword !== regConfirmPassword) {
      setError("Passwords do not match");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      await AuthApi.resetAdminPassword({
        email: regEmail,
        new_password: regPassword,
        otp: otp.trim(),
      });
      switchAdminMode("login");
      setInfoMsg("Password successfully reset! Please sign in with your new password.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setBusy(false);
    }
  }

  if (!showForms) {
    return (
      <main className="landing-shell">
        <div className="landing-hero-pill portal-selector">
          <button
            type="button"
            className="portal-btn"
            onClick={() => { switchPortal("employee"); setShowForms(true); }}
          >
            Employee Login
          </button>
          <button
            type="button"
            className="portal-btn"
            onClick={() => { switchPortal("admin"); setShowForms(true); }}
          >
            Admin Portal
          </button>
        </div>
        
        <div className="landing-info">
          <h2 className="landing-title">ACME Knowledge Assistant</h2>
          <p className="landing-subtitle">What is this project and how to use it</p>

          <Accordion title="For Admin">
            <div className="feature-grid">
              <div className="feature-item">
                <div className="feature-icon">🏢</div>
                <div className="feature-text">
                  <h4>Account & Registration</h4>
                  <p>Create your administrator account, enter your company name, and verify your identity securely via Gmail OTP.</p>
                </div>
              </div>
              
              <hr className="feature-divider" />
              
              <div className="feature-item">
                <div className="feature-icon">👥</div>
                <div className="feature-text">
                  <h4>User Management</h4>
                  <p>Seamlessly add employees and assign them to specific departments. You can reset anyone's password, toggle account access, and manage an unlimited number of users.</p>
                </div>
              </div>
              
              <hr className="feature-divider" />
              
              <div className="feature-item">
                <div className="feature-icon">📄</div>
                <div className="feature-text">
                  <h4>Documents & Access Control</h4>
                  <p>Upload an unlimited number of documents. Give strict access only to the required members or departments when uploading.</p>
                </div>
              </div>
              
              <div className="danger-alert">
                <div className="alert-icon">⚠️</div>
                <div className="feature-text">
                  <h4>Danger Zone</h4>
                  <p>You have the power to permanently delete users and documents. <strong>BEWARE:</strong> Pressing delete on your own (admin) account will wipe out the entire company and all associated data.</p>
                </div>
              </div>
            </div>
          </Accordion>

          <Accordion title="For Employee">
            <div className="feature-grid">
              <div className="feature-item">
                <div className="feature-icon">🔐</div>
                <div className="feature-text">
                  <h4>Secure Login</h4>
                  <p>Log in using your Company Name along with your Employee ID or Email and Password (ask your admin if you don't have one).</p>
                </div>
              </div>
              
              <hr className="feature-divider" />
              
              <div className="feature-item">
                <div className="feature-icon">💬</div>
                <div className="feature-text">
                  <h4>Knowledge Assistant</h4>
                  <p>Ask any queries using the smart chat interface. If you are allowed access to the relevant documents, the system will give you the answer.</p>
                </div>
              </div>
            </div>
          </Accordion>
        </div>
      </main>
    );
  }

  return (
    <main className="auth-shell">
      <div className="card auth-card">
        {/* Back button to return to landing page */}
        <button 
          type="button" 
          className="linkish" 
          onClick={() => setShowForms(false)}
          style={{ marginBottom: "1rem", display: "inline-flex", alignItems: "center", gap: "0.25rem", padding: "0" }}
        >
          ← Back to info
        </button>

        {/* Top Company Eyebrow */}
        <p className="eyebrow" style={{ textAlign: "center", marginBottom: "0.25rem" }}>
          ACME Knowledge Assistant
        </p>

        {/* Primary Role Selector Tabs */}
        <div className="portal-selector" role="tablist" aria-label="Portal Selection">
          <button
            type="button"
            className={`portal-btn ${portal === "employee" ? "active" : ""}`}
            onClick={() => switchPortal("employee")}
          >
            Employee Login
          </button>
          <button
            type="button"
            className={`portal-btn ${portal === "admin" ? "active" : ""}`}
            onClick={() => switchPortal("admin")}
          >
            Admin Portal
          </button>
        </div>

        {/* Admin Sub-Tabs (Sign In vs Create Account) */}
        {portal === "admin" && (
          <div className="sub-toggle" role="tablist">
            <button
              type="button"
              className={`sub-btn ${adminMode === "login" ? "active" : ""}`}
              onClick={() => switchAdminMode("login")}
            >
              Login to your account
            </button>
            <button
              type="button"
              className={`sub-btn ${adminMode === "register" ? "active" : ""}`}
              onClick={() => switchAdminMode("register")}
            >
              Create your account
            </button>
          </div>
        )}

        {/* Title & Description */}
        <div style={{ marginTop: "1rem", marginBottom: "1rem" }}>
          <h1 id="auth-title" style={{ fontSize: "1.4rem", margin: "0 0 0.25rem 0" }}>
            {portal === "employee"
              ? "Employee sign in"
              : adminMode === "login"
              ? "Administrator sign in"
              : adminMode === "forgot"
              ? "Reset Password"
              : "Create Administrator Account"}
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: "0.9rem" }}>
            {portal === "employee"
              ? "Use your company identifier or employee email."
              : adminMode === "login"
              ? "Use your admin credentials to access controls."
              : adminMode === "forgot"
              ? "Enter your admin email to receive a password reset code."
              : "Register as an administrator with Gmail OTP verification."}
          </p>
        </div>

        {/* Alerts & Messages */}
        {error && (
          <p role="alert" className="error" style={{ marginBottom: "1rem" }}>
            {error}
          </p>
        )}
        {infoMsg && (
          <div className="info-badge" style={{ marginBottom: "1rem" }}>
            {infoMsg}
          </div>
        )}

        {/* ─── CASE 1: Standard Login Form (Employee or Admin Sign In) ─── */}
        {(portal === "employee" || adminMode === "login") && (
          <form onSubmit={onLogin} aria-labelledby="auth-title">
            {portal === "employee" && (
              <label>
                Company Name
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  placeholder="e.g. ACME Corp"
                  required
                />
              </label>
            )}

            <label>
              Identifier or email
              <input
                autoComplete="username"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder={portal === "employee" ? "e.g. alice@acme.local or ACME-100001" : "e.g. admin@acme.local"}
                required
              />
            </label>

            <label>
              Password
              <div className="password-wrapper">
                <input
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  tabIndex={-1}
                >
                  {showPassword ? (
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
                  )}
                </button>
              </div>
              {portal === "admin" && (
                <div style={{ textAlign: "right", marginTop: "0.4rem" }}>
                  <button 
                    type="button" 
                    className="linkish" 
                    onClick={() => switchAdminMode("forgot")}
                    style={{ fontSize: "0.85rem" }}
                  >
                    Forgot password?
                  </button>
                </div>
              )}
            </label>

            <button type="submit" style={{ width: "100%", marginTop: "1rem" }} disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
        )}

        {/* ─── CASE 2: Admin Create Account (Step 1: Details & Send OTP) ─── */}
        {portal === "admin" && adminMode === "register" && !otpStep && (
          <form onSubmit={onSendOtp} aria-labelledby="auth-title">
            <label>
              Full Name
              <input
                value={regName}
                onChange={(e) => setRegName(e.target.value)}
                placeholder="e.g. Alex Johnson"
                required
              />
            </label>

            <label>
              Company Name
              <input
                value={regCompany}
                onChange={(e) => setRegCompany(e.target.value)}
                placeholder="e.g. ACME Corp"
                required
              />
            </label>

            <label>
              Gmail / Email address
              <input
                type="email"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
                placeholder="yourname@gmail.com"
                required
              />
            </label>

            <label>
              Password (min 6 characters)
              <div className="password-wrapper">
                <input
                  type={showRegPassword ? "text" : "password"}
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="Min 6 chars, 1 letter, 1 number"
                  minLength={6}
                  pattern="(?=.*[A-Za-z])(?=.*\d).+"
                  title="Password must be at least 6 characters and contain at least one letter and one number"
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowRegPassword(!showRegPassword)}
                  tabIndex={-1}
                >
                  {showRegPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </label>

            <label>
              Confirm Password
              <input
                type="password"
                value={regConfirmPassword}
                onChange={(e) => setRegConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                minLength={6}
                pattern="(?=.*[A-Za-z])(?=.*\d).+"
                title="Password must be at least 6 characters and contain at least one letter and one number"
                required
              />
            </label>

            <button type="submit" style={{ width: "100%", marginTop: "1rem" }} disabled={busy}>
              {busy ? "Sending verification code…" : "Send Verification Code"}
            </button>
          </form>
        )}

        {/* ─── CASE 3: Admin Create Account (Step 2: Enter OTP & Finish) ─── */}
        {portal === "admin" && adminMode === "register" && otpStep && (
          <form onSubmit={onVerifyOtp} aria-labelledby="auth-title">
            <div className="otp-container">
              <label style={{ textAlign: "center", marginBottom: "0.5rem" }}>
                Enter 6-digit Verification Code
                <input
                  className="otp-field"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  placeholder="••••••"
                  autoFocus
                  required
                />
              </label>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="linkish"
                  onClick={() => setOtpStep(false)}
                  style={{ fontSize: "0.85rem" }}
                >
                  ← Edit details
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={resendTimer > 0 || busy}
                  onClick={handleResendOtp}
                  style={{ fontSize: "0.85rem" }}
                >
                  {resendTimer > 0 ? `Resend in ${resendTimer}s` : "Resend code"}
                </button>
              </div>
            </div>

            <button type="submit" style={{ width: "100%", marginTop: "1.5rem" }} disabled={busy || otp.length !== 6}>
              {busy ? "Verifying…" : "Verify & Create Account"}
            </button>
          </form>
        )}

        {/* ─── CASE 4: Admin Forgot Password (Step 1: Request OTP) ─── */}
        {portal === "admin" && adminMode === "forgot" && forgotStep === 1 && (
          <form onSubmit={onSendForgotOtp} aria-labelledby="auth-title">
            <label>
              Admin Email address
              <input
                type="email"
                value={regEmail}
                onChange={(e) => setRegEmail(e.target.value)}
                placeholder="yourname@gmail.com"
                required
              />
            </label>

            <button type="submit" style={{ width: "100%", marginTop: "1rem" }} disabled={busy}>
              {busy ? "Sending reset code…" : "Send Reset Code"}
            </button>
            <div style={{ textAlign: "center", marginTop: "1rem" }}>
              <button 
                type="button" 
                className="linkish" 
                onClick={() => switchAdminMode("login")}
                style={{ fontSize: "0.85rem" }}
              >
                Back to login
              </button>
            </div>
          </form>
        )}

        {/* ─── CASE 5: Admin Forgot Password (Step 2: Enter OTP) ─── */}
        {portal === "admin" && adminMode === "forgot" && forgotStep === 2 && (
          <form onSubmit={onVerifyForgotOtp} aria-labelledby="auth-title">
            <div className="otp-container">
              <label style={{ textAlign: "center", marginBottom: "0.5rem" }}>
                Enter 6-digit Reset Code
                <input
                  className="otp-field"
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  placeholder="••••••"
                  autoFocus
                  required
                />
              </label>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "0.5rem" }}>
                <button
                  type="button"
                  className="linkish"
                  onClick={() => setForgotStep(1)}
                  style={{ fontSize: "0.85rem" }}
                >
                  ← Edit email
                </button>
                <button
                  type="button"
                  className="linkish"
                  disabled={resendTimer > 0 || busy}
                  onClick={handleResendForgotOtp}
                  style={{ fontSize: "0.85rem" }}
                >
                  {resendTimer > 0 ? `Resend in ${resendTimer}s` : "Resend code"}
                </button>
              </div>
            </div>
            <button type="submit" style={{ width: "100%", marginTop: "1.5rem" }} disabled={busy || otp.length !== 6}>
              {busy ? "Verifying…" : "Verify Code"}
            </button>
          </form>
        )}

        {/* ─── CASE 6: Admin Forgot Password (Step 3: New Password) ─── */}
        {portal === "admin" && adminMode === "forgot" && forgotStep === 3 && (
          <form onSubmit={onResetPassword} aria-labelledby="auth-title">
            <label style={{ marginTop: "1rem" }}>
              New Password (min 6 characters)
              <div className="password-wrapper">
                <input
                  type={showRegPassword ? "text" : "password"}
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  placeholder="Min 6 chars, 1 letter, 1 number"
                  minLength={6}
                  pattern="(?=.*[A-Za-z])(?=.*\d).+"
                  title="Password must be at least 6 characters and contain at least one letter and one number"
                  required
                />
                <button
                  type="button"
                  className="password-toggle"
                  onClick={() => setShowRegPassword(!showRegPassword)}
                  tabIndex={-1}
                >
                  {showRegPassword ? (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
            </label>

            <label>
              Confirm New Password
              <input
                type="password"
                value={regConfirmPassword}
                onChange={(e) => setRegConfirmPassword(e.target.value)}
                placeholder="Re-enter password"
                minLength={6}
                pattern="(?=.*[A-Za-z])(?=.*\d).+"
                title="Password must be at least 6 characters and contain at least one letter and one number"
                required
              />
            </label>

            <button type="submit" style={{ width: "100%", marginTop: "1.5rem" }} disabled={busy}>
              {busy ? "Resetting…" : "Reset Password"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
