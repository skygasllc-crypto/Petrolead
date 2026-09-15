import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../context/AuthContext";
import { PLANS } from "../components/marketing/pricing";

const PLAN_OPTIONS = PLANS.flatMap((plan) =>
  plan.tiers.map((tier) => ({
    value: `${plan.id}:${tier.credits}`,
    label: `${plan.name} — ${tier.credits.toLocaleString()} credits/mo`,
  })),
);

function planValue(subscription) {
  return subscription ? `${subscription.plan}:${subscription.credits_per_month}` : "";
}

function formatDate(value) {
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return date.toLocaleDateString();
}

function CreditAdjuster({ user, busy, onAdjust }) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const value = Number(amount);
  const valid = amount !== "" && Number.isInteger(value) && value !== 0;

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="text-xs font-semibold text-brand-600 hover:underline"
      >
        Adjust
      </button>
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!valid) return;
    if (await onAdjust(user, value)) {
      setOpen(false);
      setAmount("");
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-1 flex items-center gap-1.5">
      <input
        type="number"
        step="1"
        autoFocus
        value={amount}
        onChange={(e) => setAmount(e.target.value)}
        placeholder="+500 or -100"
        aria-label={`Credits to add or remove for ${user.email}`}
        className="w-28 rounded-md border border-base-600 bg-base-850 px-2 py-1 text-xs text-ink-100 focus:border-brand-500 focus:outline-none"
      />
      <button
        type="submit"
        disabled={busy || !valid}
        className="rounded-md bg-brand-500 px-2.5 py-1 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
      >
        Save
      </button>
      <button
        type="button"
        onClick={() => {
          setOpen(false);
          setAmount("");
        }}
        className="px-1 text-xs text-ink-500 hover:text-ink-100"
      >
        Cancel
      </button>
    </form>
  );
}

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

  function replaceUser(updated) {
    setUsers((list) => list.map((u) => (u.id === updated.id ? updated : u)));
  }

  async function runUpdate(targetUser, action, fallbackMessage) {
    setPendingId(targetUser.id);
    setError(null);
    try {
      replaceUser(await action());
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : fallbackMessage);
      return false;
    } finally {
      setPendingId(null);
    }
  }

  function toggleActive(targetUser) {
    return runUpdate(
      targetUser,
      () => api.updateUserStatus(targetUser.id, !targetUser.is_active),
      "Could not update this user.",
    );
  }

  function changePlan(targetUser, value) {
    if (value === "") {
      const confirmed = window.confirm(
        `Remove ${targetUser.email}'s plan? Their remaining credits will be removed too.`,
      );
      if (!confirmed) return;
      return runUpdate(
        targetUser,
        () => api.removeUserPlan(targetUser.id),
        "Could not remove this plan.",
      );
    }
    const [plan, credits] = value.split(":");
    return runUpdate(
      targetUser,
      () => api.setUserPlan(targetUser.id, plan, Number(credits)),
      "Could not change this plan.",
    );
  }

  function adjustCredits(targetUser, amount) {
    return runUpdate(
      targetUser,
      () => api.adjustUserCredits(targetUser.id, amount),
      "Could not adjust credits.",
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink-100">Users</h1>
        <p className="mt-1 text-sm text-ink-500">
          Everyone with access to PetroLead. Until online payments are available, put customers on
          a plan here — a new plan grants its first month of credits straight away. Blocking a
          user takes effect on their very next request.
        </p>
      </div>

      {error && (
        <div
          role="alert"
          className="rounded-lg border border-status-danger/30 bg-status-danger/10 px-4 py-3 text-sm text-status-danger"
        >
          {error}
        </div>
      )}

      {status === "loading" && <div className="text-sm text-ink-500">Loading...</div>}

      {status !== "loading" && (
        <div className="overflow-x-auto rounded-xl border border-base-700 bg-base-850">
          <table className="w-full min-w-[960px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-base-700 text-left text-xs uppercase tracking-wide text-ink-700">
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Plan</th>
                <th className="px-4 py-3 font-medium">Credits</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Joined</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = u.id === currentUser?.id;
                const busy = pendingId === u.id;
                return (
                  <tr key={u.id} className="border-b border-base-700 align-top last:border-0">
                    <td className="px-4 py-3">
                      <div className="text-ink-100">{u.email}</div>
                      {u.full_name && <div className="text-xs text-ink-500">{u.full_name}</div>}
                    </td>
                    <td className="px-4 py-3 text-ink-500">
                      {u.is_admin ? (
                        <span className="rounded-full border border-brand-500/30 bg-brand-500/15 px-2 py-0.5 text-xs font-medium text-brand-600">
                          Admin
                        </span>
                      ) : (
                        "User"
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {u.is_admin ? (
                        <span className="text-xs text-ink-500">Unlimited (admin)</span>
                      ) : (
                        <select
                          value={planValue(u.subscription)}
                          onChange={(e) => changePlan(u, e.target.value)}
                          disabled={busy}
                          aria-label={`Plan for ${u.email}`}
                          className="w-full max-w-[16rem] rounded-md border border-base-600 bg-base-850 px-2 py-1.5 text-xs text-ink-100 focus:border-brand-500 focus:outline-none disabled:opacity-60"
                        >
                          <option value="">No plan</option>
                          {PLAN_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {u.subscription ? (
                        <>
                          <div className="font-semibold text-ink-100">
                            {u.subscription.credits_balance.toLocaleString()}
                          </div>
                          <div className="text-xs text-ink-700">
                            Renews {formatDate(u.subscription.renews_at)}
                          </div>
                          <CreditAdjuster user={u} busy={busy} onAdjust={adjustCredits} />
                        </>
                      ) : (
                        <span className="text-ink-700">—</span>
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
                          disabled={busy}
                          className={`rounded-md border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
                            u.is_active
                              ? "border-status-danger/50 text-status-danger hover:bg-status-danger/10"
                              : "border-status-high/50 text-status-high hover:bg-status-high/10"
                          }`}
                        >
                          {busy ? "Working..." : u.is_active ? "Block" : "Unblock"}
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
