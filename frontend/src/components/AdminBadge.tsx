export function AdminBadge({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`badge-admin badge-${size}`} title="Administrator (Full Access)">
      <svg
        className="badge-admin-icon"
        viewBox="0 0 24 24"
        fill="currentColor"
        aria-hidden="true"
      >
        <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm-2 16l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z" />
      </svg>
      <span>ADMIN</span>
    </span>
  );
}

export function EmployeeBadge() {
  return (
    <span className="badge-employee" title="Standard Employee Account">
      <span>EMPLOYEE</span>
    </span>
  );
}
