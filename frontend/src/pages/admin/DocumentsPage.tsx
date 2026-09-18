import { FormEvent, useEffect, useState, Fragment } from "react";
import { api, type User } from "../../api";

type Acl = {
  id?: string;
  principal_type: string;
  principal_id: string | null;
  permission: string;
  department_scoped: boolean;
};

type Doc = {
  id: string;
  title: string;
  filename: string;
  ingestion_status: string;
  ingestion_error: string | null;
  department_id: string | null;
  owner_user_id: string | null;
  acls: Acl[];
};

type Org = {
  departments: Array<{ id: string; name: string }>;
  roles: Array<{ id: string; name: string }>;
  groups: Array<{ id: string; name: string }>;
};


export function DocumentsPage() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [org, setOrg] = useState<Org | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [selected, setSelected] = useState<Doc | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deleteDocId, setDeleteDocId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadAcls, setUploadAcls] = useState<Acl[]>([]);
  const [editAcls, setEditAcls] = useState<Acl[]>([]);

  async function refresh() {
    const [list, orgData, userList] = await Promise.all([
      api<Doc[]>("/api/admin/documents"),
      api<Org>("/api/admin/org"),
      api<User[]>("/api/admin/users"),
    ]);
    setDocs(list);
    setOrg(orgData);
    setUsers(userList);
  }

  useEffect(() => {
    void refresh().catch((err: Error) => setError(err.message));
  }, []);

  function AccessControlEditor({
    value,
    onChange,
  }: {
    value: Acl[];
    onChange: (next: Acl[]) => void;
  }) {
    const [expandedDepts, setExpandedDepts] = useState<Set<string>>(new Set());

    const selectedDepts = new Set(
      value.filter((a) => a.principal_type === "DEPARTMENT").map((a) => a.principal_id)
    );
    const selectedUsers = new Set(
      value.filter((a) => a.principal_type === "USER").map((a) => a.principal_id)
    );

    const toggleDepartmentAcl = (deptId: string, checked: boolean) => {
      let next = value.filter(
        (a) =>
          !(a.principal_type === "DEPARTMENT" && a.principal_id === deptId) &&
          !(a.principal_type === "USER" && users.find((u) => u.id === a.principal_id)?.department_id === deptId)
      );

      if (checked) {
        next.push({ principal_type: "DEPARTMENT", principal_id: deptId, permission: "READ", department_scoped: false });
      }
      onChange(next);
    };

    const toggleUserAcl = (userId: string, deptId: string, checked: boolean) => {
      const deptUsers = users.filter((u) => u.department_id === deptId);
      const isDeptSelected = value.some((a) => a.principal_type === "DEPARTMENT" && a.principal_id === deptId);
      
      let next = [...value];

      if (isDeptSelected && !checked) {
        next = next.filter((a) => !(a.principal_type === "DEPARTMENT" && a.principal_id === deptId));
        deptUsers.forEach((u) => {
          if (u.id !== userId) {
            next.push({ principal_type: "USER", principal_id: u.id, permission: "READ", department_scoped: false });
          }
        });
      } else if (!isDeptSelected && checked) {
        next.push({ principal_type: "USER", principal_id: userId, permission: "READ", department_scoped: false });
        
        const selectedUserIds = new Set(next.filter((a) => a.principal_type === "USER").map((a) => a.principal_id));
        const allSelected = deptUsers.length > 0 && deptUsers.every((u) => selectedUserIds.has(u.id));
        
        if (allSelected) {
          next = next.filter((a) => !(a.principal_type === "USER" && deptUsers.some((u) => u.id === a.principal_id)));
          next.push({ principal_type: "DEPARTMENT", principal_id: deptId, permission: "READ", department_scoped: false });
        }
      } else if (!isDeptSelected && !checked) {
        next = next.filter((a) => !(a.principal_type === "USER" && a.principal_id === userId));
      }
      
      onChange(next);
    };

    const toggleExpand = (deptId: string) => {
      const next = new Set(expandedDepts);
      if (next.has(deptId)) {
        next.delete(deptId);
      } else {
        next.add(deptId);
      }
      setExpandedDepts(next);
    };

    return (
      <fieldset className="card compact">
        <legend>Access Control</legend>
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {org?.departments.length === 0 ? (
            <span className="muted" style={{ fontSize: "0.9em" }}>No departments found. Please create one in the Users page.</span>
          ) : null}
          {org?.departments.map((dept) => {
            const isExpanded = expandedDepts.has(dept.id);
            const deptUsers = users.filter((u) => u.department_id === dept.id);
            const isDeptSelected = selectedDepts.has(dept.id);
            
            return (
              <div key={dept.id} style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
                  <label className="inline" style={{ margin: 0, fontWeight: "bold" }}>
                    <input 
                      type="checkbox" 
                      checked={isDeptSelected} 
                      onChange={(e) => toggleDepartmentAcl(dept.id, e.target.checked)} 
                    />
                    {dept.name}
                  </label>
                  <button 
                    type="button" 
                    className="linkish" 
                    onClick={() => toggleExpand(dept.id)}
                  >
                    {isExpanded ? "Hide Employees" : `Show Employees (${deptUsers.length})`}
                  </button>
                </div>
                
                {isExpanded && (
                  <div style={{ paddingLeft: "1.5rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
                    {deptUsers.length === 0 ? (
                      <span className="muted" style={{ fontSize: "0.9em" }}>No employees found</span>
                    ) : (
                      deptUsers.map((user) => (
                        <label key={user.id} className="inline" style={{ margin: 0 }}>
                          <input 
                            type="checkbox" 
                            checked={isDeptSelected || selectedUsers.has(user.id)} 
                            onChange={(e) => toggleUserAcl(user.id, dept.id, e.target.checked)}
                          />
                          {user.full_name} <span className="muted">({user.email})</span>
                        </label>
                      ))
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </fieldset>
    );
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    body.append("title", title);
    body.append("document_type", "file");
    body.append("acls_json", JSON.stringify(uploadAcls));
    try {
      await api("/api/admin/documents", { method: "POST", body });
      setTitle("");
      setFile(null);
      setUploadAcls([]);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process request");
    }
  }

  async function openDoc(id: string) {
    const doc = await api<Doc>(`/api/admin/documents/${id}`);
    setSelected(doc);
    setEditAcls(doc.acls.map((a) => ({ ...a })));
  }

  async function saveAcls(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    await api(`/api/admin/documents/${selected.id}`, {
      method: "PATCH",
      body: JSON.stringify({ acls: editAcls }),
    });
    await refresh();
    await openDoc(selected.id);
  }

  async function reindex(id: string) {
    await api(`/api/admin/documents/${id}/reindex`, { method: "POST" });
    await refresh();
  }

  async function toggleDisable(id: string, disable: boolean) {
    await api(`/api/admin/documents/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ disabled: disable }),
    });
    await refresh();
  }

  async function deleteDoc(doc: Doc) {
    try {
      await api(`/api/admin/documents/${doc.id}`, { method: "DELETE" });
      if (selected?.id === doc.id) setSelected(null);
      setDeleteDocId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process request");
    }
  }

  return (
    <div>
      <h1>Documents</h1>
      {error ? <p className="error">{error}</p> : null}
      <form className="card compact" onSubmit={upload}>
        <h2>Upload</h2>
        <label>
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} required />
        </label>
        <AccessControlEditor value={uploadAcls} onChange={setUploadAcls} />
        <label>
          File
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} required />
        </label>
        <button type="submit">Upload and ingest</button>
      </form>
      <table>
        <thead>
          <tr>
            <th>Title</th>
            <th>File</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc) => (
            <Fragment key={doc.id}>
              <tr>
                <td>{doc.title}</td>
                <td>{doc.filename}</td>
                <td>{doc.ingestion_status}{doc.ingestion_error ? ` (${doc.ingestion_error})` : ""}</td>
                <td>
                  <button className="linkish" onClick={() => void openDoc(doc.id)}>ACL</button>
                  <button className="linkish" onClick={() => void reindex(doc.id)}>Re-index</button>
                  {doc.ingestion_status === "DISABLED" ? (
                    <button className="linkish" onClick={() => void toggleDisable(doc.id, false)}>Enable</button>
                  ) : (
                    <button className="linkish" onClick={() => void toggleDisable(doc.id, true)}>Disable</button>
                  )}
                  <button className="linkish danger" onClick={() => setDeleteDocId(doc.id)}>Delete</button>
                </td>
              </tr>
              {deleteDocId === doc.id && (
                <tr>
                  <td colSpan={4} style={{ padding: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.5rem 1rem", background: "var(--bg-card)", borderTop: "1px solid var(--border)" }}>
                      <span>Are you sure you want to delete document <strong>{doc.title}</strong>? This action cannot be undone.</span>
                      <button className="danger" onClick={() => void deleteDoc(doc)}>Yes, Delete</button>
                      <button onClick={() => setDeleteDocId(null)}>Cancel</button>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
      {selected ? (
        <form className="card" onSubmit={(event) => void saveAcls(event)}>
          <h2>Access policy: {selected.title}</h2>
          <AccessControlEditor value={editAcls} onChange={setEditAcls} />
          <button type="submit">Save ACL</button>
        </form>
      ) : null}
    </div>
  );
}
