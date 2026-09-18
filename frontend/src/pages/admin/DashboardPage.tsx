import { useEffect, useState } from "react";
import { api } from "../../api";

type Dashboard = {
  total_users: number;
  active_users: number;
  documents: number;
  failed_ingestions: number;
  recent_security_events: Array<{
    id: string;
    timestamp: string | null;
    action: string;
    name: string;
    new_password?: string;
  }>;
};

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Dashboard>("/api/admin/dashboard")
      .then(setData)
      .catch((err: Error) => setError(err.message));
  }, []);



  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading dashboard…</p>;

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="stats">
        <article><h2>{data.total_users}</h2><p>Total users</p></article>
        <article><h2>{data.active_users}</h2><p>Active users</p></article>
        <article><h2>{data.documents}</h2><p>Documents</p></article>
        <article><h2>{data.failed_ingestions}</h2><p>Failed ingestions</p></article>
      </div>
      <h2>Recent employee password changes</h2>
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>Time</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {data.recent_security_events.map((event) => (
            <tr key={event.id}>
              <td>{event.name}</td>
              <td>{event.timestamp ? new Date(event.timestamp).toLocaleString(undefined, { timeZone: "Asia/Kolkata" }) : "N/A"}</td>
              <td>{event.action.replace("_", " ")}</td>
            </tr>
          ))}
          {data.recent_security_events.length === 0 && (
            <tr>
              <td colSpan={3} style={{ textAlign: "center", padding: "1rem" }}>No recent employee password changes.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
