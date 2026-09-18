import { useEffect, useState } from "react";
import { api } from "../../api";

type Log = {
  id: string;
  timestamp: string | null;
  actor_user_id: string | null;
  actor_name?: string | null;
  action: string;
  status: string;
  request_id: string;
  document_id: string | null;
  target?: string | null;
};

const ACTION_MAP: Record<string, string> = {
  admin_login: "Admin login",
  employee_login: "Employee login",
  employee_logout: "Employee logout",
  admin_logout: "Admin logout",
  forget_password: "Forgot password",
  new_password: "New password",
  change_password: "Change password",
  reset_password: "Password reset",
  download_document: "Employee downloaded document",
  upload_document: "New document added by admin",
  delete_document: "Document removed",
  patch_document: "Document updated",
  create_user: "User added",
  delete_user: "User removed",
  create_department: "Department added",
  delete_department: "Department removed",
  patch_user: "User updated",
  reindex_document: "Document reindexed",
};

function formatAction(action: string) {
  if (ACTION_MAP[action]) {
    return ACTION_MAP[action];
  }
  return action
    .split("_")
    .map((word, index) => (index === 0 ? word.charAt(0).toUpperCase() + word.slice(1) : word))
    .join(" ");
}

function formatDate(isoString: string | null) {
  if (!isoString) return "N/A";
  const date = new Date(isoString);
  return date.toLocaleString(undefined, { timeZone: "Asia/Kolkata" });
}

export function AuditPage() {
  const [logs, setLogs] = useState<Log[]>([]);
  useEffect(() => {
    void api<Log[]>("/api/admin/audit-logs").then(setLogs);
  }, []);
  return (
    <div>
      <h1>Audit logs</h1>
      <table>
        <thead>
          <tr>
            <th>Time</th>
            <th>Actor</th>
            <th>Action</th>
            <th>Status</th>
            <th>Request</th>
            <th>Target</th>
            <th>Resource</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((log) => (
            <tr key={log.id}>
              <td>{formatDate(log.timestamp)}</td>
              <td>{log.actor_name || log.actor_user_id || "System"}</td>
              <td>{formatAction(log.action)}</td>
              <td>{log.status}</td>
              <td>{log.request_id}</td>
              <td>{log.target || "-"}</td>
              <td>{log.document_id || "N/A"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
