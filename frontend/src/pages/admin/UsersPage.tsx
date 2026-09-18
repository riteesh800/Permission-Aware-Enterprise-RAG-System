import { FormEvent, useEffect, useState, Fragment } from "react";
import { api, type User } from "../../api";
import { AdminBadge, EmployeeBadge } from "../../components/AdminBadge";

type Org = {
  departments: Array<{ id: string; name: string }>;
  roles: Array<{ id: string; name: string }>;
  groups: Array<{ id: string; name: string }>;
};

type UserDetail = User & {
  access_summary?: Record<string, unknown>;
};

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [org, setOrg] = useState<Org | null>(null);
  const [selected, setSelected] = useState<UserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selfDeleteUser, setSelfDeleteUser] = useState<User | null>(null);
  const [selfDeleteMethod, setSelfDeleteMethod] = useState<"password" | "otp" | null>(null);
  const [selfDeleteCredential, setSelfDeleteCredential] = useState("");
  const [selfDeleteToken, setSelfDeleteToken] = useState<string | null>(null);
  const [selfDeleteOtpSent, setSelfDeleteOtpSent] = useState(false);
  const [selfDeleteError, setSelfDeleteError] = useState<string | null>(null);
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    password: "TempPassw0rd!x",
    department_id: "",
  });
  const [edit, setEdit] = useState({
    full_name: "",
    department_id: "",
  });

  const [createDeptName, setCreateDeptName] = useState("");
  const [editDeptName, setEditDeptName] = useState("");

  const [resetPasswordUserId, setResetPasswordUserId] = useState<string | null>(null);
  const [resetPasswordInput, setResetPasswordInput] = useState("");
  const [resetPasswordError, setResetPasswordError] = useState<string | null>(null);
  const [deleteUserId, setDeleteUserId] = useState<string | null>(null);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);

  async function refresh() {
    const [list, orgData] = await Promise.all([
      api<User[]>("/api/admin/users"),
      api<Org>("/api/admin/org"),
    ]);
    setUsers(list);
    setOrg(orgData);
    if (!form.department_id && orgData.departments.length > 0) {
      setForm(prev => ({ ...prev, department_id: orgData.departments[0].id }));
    }
  }

  useEffect(() => {
    void refresh().catch((err: Error) => setError(err.message));
  }, []);

  async function createDepartment(name: string): Promise<string | null> {
    try {
      const res = await api<{id: string, name: string}>("/api/admin/org/departments", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      await refresh();
      return res.id;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create department");
      return null;
    }
  }

  async function createUser(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          department_id: form.department_id || null,
        }),
      });
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process request");
    }
  }

  async function openUser(id: string) {
    const detail = await api<UserDetail>(`/api/admin/users/${id}`);
    setSelected(detail);
    setEdit({
      full_name: detail.full_name,
      department_id: detail.department_id || "",
    });
  }

  async function saveUser(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await api(`/api/admin/users/${selected.id}`, {
      method: "PATCH",
      body: JSON.stringify({
        full_name: edit.full_name,
        department_id: edit.department_id || null,
      }),
    });
    await refresh();
    await openUser(selected.id);
  }

  async function toggleActive(user: User) {
    await api(`/api/admin/users/${user.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !user.is_active }),
    });
    await refresh();
  }

  async function submitResetPassword(user: User) {
    if (resetPasswordInput.length < 6 || !/[a-zA-Z]/.test(resetPasswordInput) || !/\d/.test(resetPasswordInput)) {
      setResetPasswordError("Password must be at least 6 characters and contain at least one letter and one number");
      return;
    }
    try {
      await api(`/api/admin/users/${user.id}/reset-password`, {
        method: "POST",
        body: JSON.stringify({ password: resetPasswordInput, must_change_password: true }),
      });
      setInfoMsg(`Password for ${user.full_name} has been reset.`);
      setResetPasswordUserId(null);
      setResetPasswordInput("");
      setResetPasswordError(null);
    } catch (err) {
      setResetPasswordError(err instanceof Error ? err.message : "Failed to reset password");
    }
  }

  async function deleteUser(user: User, payload?: { token?: string }) {
    try {
      await api(`/api/admin/users/${user.id}`, { 
        method: "DELETE",
        body: payload ? JSON.stringify(payload) : undefined
      });
      if (selected?.id === user.id) setSelected(null);
      setSelfDeleteUser(null);
      setDeleteUserId(null);
      setInfoMsg(`User ${user.full_name} deleted.`);
      await refresh();
      if (payload?.token) {
        // If we deleted ourselves, reload to redirect to login
        window.location.reload();
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unable to process request";
      if (msg === "Must confirm deletion with 'DELETE'" || msg === "Invalid password" || msg === "Missing deletion verification token") {
        setSelfDeleteUser(user);
        setSelfDeleteError("Verification required to delete admin account");
      } else {
        setError(msg);
      }
    }
  }

  async function sendDeleteOtp() {
    setSelfDeleteError(null);
    try {
      await api("/api/auth/delete-account/send-otp", { method: "POST" });
      setSelfDeleteOtpSent(true);
      setInfoMsg("OTP sent to your email.");
    } catch (err) {
      setSelfDeleteError(err instanceof Error ? err.message : "Failed to send OTP");
    }
  }

  async function verifyDeleteCredential(e: FormEvent) {
    e.preventDefault();
    setSelfDeleteError(null);
    if (!selfDeleteUser) return;
    
    try {
      const body: any = {};
      if (selfDeleteMethod === "password") body.password = selfDeleteCredential;
      if (selfDeleteMethod === "otp") body.otp = selfDeleteCredential;
      
      const res = await api<{ token: string }>(`/api/admin/users/${selfDeleteUser.id}/verify-delete`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setSelfDeleteToken(res.token);
    } catch (err) {
      setSelfDeleteError(err instanceof Error ? err.message : "Verification failed");
    }
  }

  return (
    <div>
      <h1>Users</h1>
      {error ? <p className="error">{error}</p> : null}
      {infoMsg ? <p className="info-badge">{infoMsg}</p> : null}
      
      {selfDeleteUser ? (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          width: "100vw",
          height: "100vh",
          backgroundColor: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000
        }}>
          <div className="card compact" style={{ border: "2px solid var(--danger)", width: "100%", maxWidth: "500px" }}>
            <h2 style={{ color: "var(--danger)", marginTop: 0 }}>Delete Company Account</h2>
            <p style={{ fontWeight: 'bold' }}>WARNING: This action is permanent and cannot be undone.</p>
            <p>You are about to permanently delete your admin account, all employees, all documents, chat histories, logs, and all configurations. Everything will be wiped completely.</p>
            {selfDeleteError && <p className="error" style={{ marginBottom: "1rem" }}>{selfDeleteError}</p>}
            
            {!selfDeleteToken ? (
              <form onSubmit={verifyDeleteCredential}>
                {!selfDeleteMethod ? (
                  <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
                    <button type="button" onClick={() => setSelfDeleteMethod("password")}>Verify with Password</button>
                    <button type="button" onClick={() => setSelfDeleteMethod("otp")}>Verify with Email OTP</button>
                  </div>
                ) : (
                  <>
                    <label>
                      {selfDeleteMethod === "password" ? "Enter your password" : "Enter Email OTP"}
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <input 
                          type={selfDeleteMethod === "password" ? "password" : "text"} 
                          value={selfDeleteCredential} 
                          onChange={e => setSelfDeleteCredential(e.target.value)} 
                          required 
                          style={{ flex: 1, margin: 0 }}
                        />
                        {selfDeleteMethod === "otp" && !selfDeleteOtpSent && (
                          <button type="button" onClick={() => void sendDeleteOtp()}>Send OTP</button>
                        )}
                      </div>
                    </label>
                    <div style={{ display: "flex", gap: "1rem", marginTop: "1.5rem" }}>
                      <button type="submit" style={{ flex: 1 }}>Verify Identity</button>
                    </div>
                  </>
                )}
              </form>
            ) : (
              <div style={{ marginTop: "1.5rem", padding: "1rem", background: "rgba(255,0,0,0.1)", borderRadius: "8px" }}>
                <p>Identity verified. Are you absolutely sure you want to permanently delete this company?</p>
                <div style={{ display: "flex", gap: "1rem", marginTop: "1rem" }}>
                  <button className="danger" style={{ flex: 1 }} onClick={() => void deleteUser(selfDeleteUser, { token: selfDeleteToken })}>
                    Delete Permanently
                  </button>
                </div>
              </div>
            )}
            
            <div style={{ display: "flex", justifyContent: "center", marginTop: "1rem" }}>
              <button className="linkish" onClick={() => {
                setSelfDeleteUser(null);
                setSelfDeleteMethod(null);
                setSelfDeleteCredential("");
                setSelfDeleteToken(null);
                setSelfDeleteError(null);
              }}>Cancel</button>
            </div>
          </div>
        </div>
      ) : null}

      <form className="card compact" onSubmit={createUser}>
        <h2>Create user</h2>
        <label>
          Full name
          <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} minLength={1} maxLength={200} required />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} minLength={3} maxLength={320} required />
        </label>
        <label>
          Temporary password
          <input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} minLength={6} maxLength={256} pattern="(?=.*[A-Za-z])(?=.*\d).+" title="Password must be at least 6 characters and contain at least one letter and one number" required />
        </label>
        <label>
          Department
          <select 
            value={form.department_id} 
            onChange={(e) => setForm({ ...form, department_id: e.target.value })}
            required
          >
            <option value="" disabled>Select a department...</option>
            {org?.departments.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
            <option value="__new__">+ Create new department...</option>
          </select>
        </label>
        {form.department_id === "__new__" && (
          <div style={{ display: "flex", gap: "0.5rem", marginTop: "-0.5rem", marginBottom: "1rem" }}>
            <input 
              placeholder="New department name"
              value={createDeptName}
              onChange={(e) => setCreateDeptName(e.target.value)}
              style={{ flex: 1, margin: 0 }}
            />
            <button 
              type="button" 
              onClick={async () => {
                if (createDeptName.trim()) {
                  const newId = await createDepartment(createDeptName.trim());
                  if (newId) {
                    setForm({ ...form, department_id: newId });
                    setCreateDeptName("");
                  }
                }
              }}
            >
              Add
            </button>
            <button type="button" className="danger" onClick={() => { setForm({ ...form, department_id: "" }); setCreateDeptName(""); }}>Cancel</button>
          </div>
        )}
        <button type="submit">Create</button>
      </form>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Role</th>
            <th>Email</th>
            <th>Active</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <Fragment key={user.id}>
              <tr>
                <td><code>{user.unique_identifier}</code></td>
                <td><strong>{user.full_name}</strong></td>
                <td>
                  {user.app_role === "ADMIN" ? (
                    <AdminBadge size="sm" />
                  ) : (
                    <EmployeeBadge />
                  )}
                </td>
                <td>{user.email}</td>
                <td>{user.is_active ? "Yes" : "No"}</td>
                <td>
                  <button className="linkish" onClick={() => void openUser(user.id)}>Edit</button>
                  <button className="linkish" onClick={() => void toggleActive(user)}>
                    {user.is_active ? "Disable" : "Enable"}
                  </button>
                  <button className="linkish" onClick={() => {
                    setResetPasswordUserId(user.id);
                    setResetPasswordInput("");
                    setResetPasswordError(null);
                    setDeleteUserId(null);
                    setInfoMsg(null);
                    setError(null);
                  }}>Reset password</button>
                  <button className="linkish danger" onClick={() => {
                    setDeleteUserId(user.id);
                    setResetPasswordUserId(null);
                    setResetPasswordError(null);
                    setInfoMsg(null);
                    setError(null);
                  }}>Delete</button>
                </td>
              </tr>
              {resetPasswordUserId === user.id && (
                <tr>
                  <td colSpan={6} style={{ padding: 0 }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", padding: "0.5rem 1rem", background: "var(--bg-card)", borderTop: "1px solid var(--border)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span>New password for <strong>{user.full_name}</strong>:</span>
                        <input 
                          type="text" 
                          value={resetPasswordInput} 
                          onChange={e => setResetPasswordInput(e.target.value)} 
                          placeholder="Min 6 chars, 1 letter, 1 number" 
                          style={{ margin: 0 }}
                        />
                        <button onClick={() => void submitResetPassword(user)}>Confirm Reset</button>
                        <button className="danger" onClick={() => setResetPasswordUserId(null)}>Cancel</button>
                      </div>
                      {resetPasswordError && <p className="error" style={{ margin: 0 }}>{resetPasswordError} <small>(Refresh page if you get error)</small></p>}
                    </div>
                  </td>
                </tr>
              )}
              {deleteUserId === user.id && (
                <tr>
                  <td colSpan={6} style={{ padding: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.5rem 1rem", background: "var(--bg-card)", borderTop: "1px solid var(--border)" }}>
                      <span>Are you sure you want to delete <strong>{user.full_name}</strong>? This action cannot be undone.</span>
                      <button className="danger" onClick={() => void deleteUser(user)}>Yes, Delete</button>
                      <button onClick={() => setDeleteUserId(null)}>Cancel</button>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
      {selected ? (
        <form className="card" onSubmit={(event) => void saveUser(event)}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.75rem", marginBottom: "0.75rem" }}>
            <h2 style={{ margin: 0 }}>Edit {selected.unique_identifier}</h2>
            {selected.app_role === "ADMIN" ? (
              <AdminBadge size="sm" />
            ) : (
              <EmployeeBadge />
            )}
          </div>
          <label>
            Full name
            <input value={edit.full_name} onChange={(e) => setEdit({ ...edit, full_name: e.target.value })} minLength={1} maxLength={200} required />
          </label>
          <label>
            Department
            <select 
              value={edit.department_id} 
              onChange={(e) => setEdit({ ...edit, department_id: e.target.value })}
              required={selected?.app_role !== "ADMIN"}
            >
              {selected?.app_role === "ADMIN" ? <option value="">None</option> : <option value="" disabled>Select a department...</option>}
              {org?.departments.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
              <option value="__new__">+ Create new department...</option>
            </select>
          </label>
          {edit.department_id === "__new__" && (
            <div style={{ display: "flex", gap: "0.5rem", marginTop: "-0.5rem", marginBottom: "1rem" }}>
              <input 
                placeholder="New department name"
                value={editDeptName}
                onChange={(e) => setEditDeptName(e.target.value)}
                style={{ flex: 1, margin: 0 }}
              />
              <button 
                type="button" 
                onClick={async () => {
                  if (editDeptName.trim()) {
                    const newId = await createDepartment(editDeptName.trim());
                    if (newId) {
                      setEdit({ ...edit, department_id: newId });
                      setEditDeptName("");
                    }
                  }
                }}
              >
                Add
              </button>
              <button type="button" className="danger" onClick={() => { setEdit({ ...edit, department_id: "" }); setEditDeptName(""); }}>Cancel</button>
            </div>
          )}
          <p>Authorized documents: {String(selected.access_summary?.authorized_document_count ?? "")}</p>
          <button type="submit">Save permissions</button>
        </form>
      ) : null}
    </div>
  );
}
