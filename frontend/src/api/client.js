const API_BASE = "/api";

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new ApiError(
      "Could not reach the PetroLead server. Check that the backend is running.",
      0,
    );
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // non-JSON error body — keep the generic message
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return null;
  return response.json();
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

  discover: (payload) =>
    request("/discover", { method: "POST", body: JSON.stringify(payload) }),

  listCompanies: (params = {}) => request(`/companies${toQuery(params)}`),

  getCompany: (id) => request(`/companies/${id}`),

  listSearches: (params = {}) => request(`/searches${toQuery(params)}`),
};

export { ApiError };
