import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function AdminUsers() {
  const { user: currentUser } = useAuth();
  const [status, setStatus] = useState("loading"); // loading | done | error
  const [error, setError] = useState(null);
  const [users, setUsers] = useState([]);
  const [pendingId, setPendingId] = useState(null);

  async function load() {
    setStatus("loading");
    setError(null);
    try {
      const result = await api.listUsers();
      setUsers(result);
      setStatus("done");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setStatus("error");
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function toggleActive(targetUser) {
    setPendingId(targetUser.id);
    try {
      const updated = await api.updateUserStatus(targetUser.id, !targetUser.is_active);
      setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update this user.");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Users</h1>
        <p className="mt-1 text-sm text-ink-500">
          Everyone with access to PetroLead. Blocking a user takes effect immediately — their
          current session stops working on their very next request, not just their next login.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger">
          {error}
        </div>
      )}

      {status === "loading" && <div className="text-sm text-ink-500">Loading...</div>}

      {status !== "loading" && (
        <div className="overflow-x-auto rounded-xl border border-base-700 bg-base-850">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-base-700 text-left text-xs uppercase tracking-wide text-ink-700">
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Joined</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                return (
                  <tr key={u.id} className="border-b border-base-800 last:border-0">
                    <td className="px-4 py-3 text-ink-100">{u.email}</td>
                    <td className="px-4 py-3 text-ink-500">{u.full_name || "—"}</td>
                    <td className="px-4 py-3 text-ink-500">
                      {u.is_admin ? (
                        <span className="rounded-full border border-brass-500/30 bg-brass-500/15 px-2 py-0.5 text-xs font-medium text-brass-300">
                          Admin
                        </span>
                      ) : (
                        "User"
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_active ? (
                        <span className="rounded-full border border-status-high/30 bg-status-high/15 px-2 py-0.5 text-xs font-medium text-status-high">
                          Active
                        </span>
                      ) : (
                        <span className="rounded-full border border-status-danger/30 bg-status-danger/15 px-2 py-0.5 text-xs font-medium text-status-danger">
                          Blocked
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-ink-500">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isSelf ? (
                        <span className="text-xs text-ink-700">This is you</span>
                      ) : (
                        <button
                          type="button"
                          onClick={() => toggleActive(u)}
                          disabled={pendingId === u.id}
                          className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                            u.is_active
                              ? "border-status-danger/50 text-status-danger hover:bg-status-danger/10"
                              : "border-status-high/50 text-status-high hover:bg-status-high/10"
                          }`}
                        >
                          {pendingId === u.id
                            ? "Working..."
                            : u.is_active
                              ? "Block"
                              : "Unblock"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
