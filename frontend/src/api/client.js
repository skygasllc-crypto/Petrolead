const API_BASE = "/api";
const TOKEN_STORAGE_KEY = "petrolead_token";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized = null;

/** Called once by AuthContext so a 401 anywhere logs the user out. */
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

export function getToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

function authHeaders() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseErrorDetail(response) {
  let detail = `Request failed (${response.status})`;
  try {
    const body = await response.json();
    detail = body.detail || detail;
  } catch {
    // non-JSON error body — keep the generic message
  }
  return detail;
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json", ...authHeaders() },
      ...options,
    });
  } catch {
    throw new ApiError(
      "Could not reach the PetroLead server. Check that the backend is running.",
      0,
    );
  }

  if (response.status === 401 && onUnauthorized) onUnauthorized();

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }

  if (response.status === 204) return null;
  return response.json();
}

/** Fetch a file download with auth headers attached, then trigger a save —
 * a plain <a href> can't carry an Authorization header. */
async function requestDownload(path, params = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}${toQuery(params)}`, { headers: authHeaders() });
  } catch {
    throw new ApiError(
      "Could not reach the PetroLead server. Check that the backend is running.",
      0,
    );
  }

  if (response.status === 401 && onUnauthorized) onUnauthorized();
  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }

  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : "download";
  const blob = await response.blob();

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function toQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, value);
  });
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const api = {
  health: () => request("/health"),

  register: (payload) =>
    request("/auth/register", { method: "POST", body: JSON.stringify(payload) }),

  login: (payload) => request("/auth/login", { method: "POST", body: JSON.stringify(payload) }),

  me: () => request("/auth/me"),

  discover: (payload) =>
    request("/discover", { method: "POST", body: JSON.stringify(payload) }),

  discoverFromUrl: (url) =>
    request("/discover-url", { method: "POST", body: JSON.stringify({ url }) }),

  bulkContactLookup: (items) =>
    request("/contacts/bulk-lookup", { method: "POST", body: JSON.stringify({ items }) }),

  saveCompany: (payload) =>
    request("/companies/save", { method: "POST", body: JSON.stringify(payload) }),

  saveCompaniesBulk: (companies) =>
    request("/companies/save-bulk", { method: "POST", body: JSON.stringify({ companies }) }),

  listCompanies: (params = {}) => request(`/companies${toQuery(params)}`),

  getCompany: (id) => request(`/companies/${id}`),

  listSearches: (params = {}) => request(`/searches${toQuery(params)}`),

  exportCompanies: (params = {}) => requestDownload("/companies/export", params),

  listEmails: (params = {}) => request(`/emails${toQuery(params)}`),

  exportEmails: (params = {}) => requestDownload("/emails/export", params),

  listSavedSearches: () => request("/saved-searches"),

  createSavedSearch: (payload) =>
    request("/saved-searches", { method: "POST", body: JSON.stringify(payload) }),

  setSavedSearchActive: (id, isActive) =>
    request(`/saved-searches/${id}${toQuery({ is_active: isActive })}`, {
      method: "PATCH",
    }),

  deleteSavedSearch: (id) => request(`/saved-searches/${id}`, { method: "DELETE" }),

  runDueSavedSearches: () => request("/saved-searches/run-due", { method: "POST" }),

  listUsers: () => request("/admin/users"),

  updateUserStatus: (userId, isActive) =>
    request(`/admin/users/${userId}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    }),
};

export { ApiError };
