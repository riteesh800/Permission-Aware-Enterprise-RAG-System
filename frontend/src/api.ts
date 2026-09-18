export type User = {
  id: string;
  unique_identifier: string;
  email: string;
  full_name: string;
  app_role: "ADMIN" | "EMPLOYEE";
  department_id: string | null;
  is_active: boolean;
  must_change_password: boolean;
  role_names: string[];
  group_names: string[];
  role_ids?: string[];
  group_ids?: string[];
  company_name?: string | null;
};

export type Citation = {
  title: string;
  page: number | null;
  section: string | null;
  source_id: string;
};

function csrfToken(): string | null {
  const match = document.cookie.match(/(?:^|; )csrf_token=([^;]*)/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.error === "string") return body.error;
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch {
    /* ignore */
  }
  if (response.status === 401) return "Unauthorized";
  if (response.status === 403) return "Forbidden";
  return "Unable to process request";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  let csrf = csrfToken();
  if (csrf) headers.set("X-CSRF-Token", csrf);
  
  let response = await fetch(path, { ...init, headers, credentials: "include" });
  
  if (response.status === 401 && path !== "/api/auth/refresh" && path !== "/api/auth/login") {
    // Attempt to refresh the session
    const refreshRes = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: { "X-CSRF-Token": csrf || "" },
      credentials: "include"
    });
    
    if (refreshRes.ok) {
      // Re-fetch the new CSRF token if it changed
      csrf = csrfToken();
      if (csrf) headers.set("X-CSRF-Token", csrf);
      // Retry original request
      response = await fetch(path, { ...init, headers, credentials: "include" });
    }
  }

  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const AuthApi = {
  login: (identifier: string, password: string, companyName?: string) =>
    api<{ user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ identifier, password, company_name: companyName }),
    }),
  logout: () => api<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  me: () => api<User>("/api/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    api<{ ok: boolean }>("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify({ current_password, new_password }),
    }),
  sendAdminOtp: (email: string) =>
    api<{ ok: boolean; message: string }>("/api/auth/register-admin/send-otp", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  verifyAdminOtp: (payload: { full_name: string; email: string; password: string; otp: string; company_name: string }) =>
    api<{ user: User }>("/api/auth/register-admin/verify", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  sendAdminForgotPasswordOtp: (email: string) =>
    api<{ ok: boolean; message: string }>("/api/auth/forgot-password/send-otp", {
      method: "POST",
      body: JSON.stringify({ email }),
    }),
  verifyAdminForgotPasswordOtp: (email: string, otp: string) =>
    api<{ ok: boolean; message: string }>("/api/auth/forgot-password/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email, otp }),
    }),
  resetAdminPassword: (payload: { email: string; otp: string; new_password: string }) =>
    api<{ ok: boolean; message: string }>("/api/auth/forgot-password/reset", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};

export const EmployeeApi = {
  getDocuments: () => api<any[]>("/api/employee/documents"),
  downloadDocumentUrl: (documentId: string) => `/api/employee/documents/${documentId}/download`,
};

