import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, ApiError } from "../api/client";
import Logo from "../components/Logo";
import ErrorBanner from "../components/ErrorBanner";

const inputClasses =
  "w-full rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brand-500 focus:outline-none";

const MIN_PASSWORD_LENGTH = 8;

export default function ResetPassword() {
  const { applyAuthResult } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (password !== confirm) {
      setError("The two passwords don't match.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      // Signs in with the new password, and ends every other session.
      applyAuthResult(await api.resetPassword(token, password));
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-brand-50 to-base-850 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex justify-center">
          <Link to="/" aria-label="PetroLead home">
            <Logo />
          </Link>
        </div>
        <div className="rounded-2xl border border-base-700 bg-base-850 p-8 shadow-lg">
          <h1 className="text-lg font-semibold text-ink-100">Choose a new password</h1>
          {!token ? (
            <p className="mt-3 text-sm text-ink-500">
              This link is missing its reset code. Open the link from your email again, or{" "}
              <Link to="/forgot-password" className="text-brand-600 hover:underline">
                ask for a new one
              </Link>
              .
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-ink-700">
                  New password
                </span>
                <input
                  type="password"
                  required
                  minLength={MIN_PASSWORD_LENGTH}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClasses}
                  placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
                />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-ink-700">
                  Confirm new password
                </span>
                <input
                  type="password"
                  required
                  minLength={MIN_PASSWORD_LENGTH}
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className={inputClasses}
                />
              </label>

              {error && <ErrorBanner message={error} />}

              <button
                type="submit"
                disabled={submitting}
                className="mt-2 inline-flex items-center justify-center rounded-md bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? "Saving..." : "Set New Password"}
              </button>
            </form>
          )}
        </div>
        <p className="mt-4 text-center text-sm text-ink-500">
          Link expired?{" "}
          <Link to="/forgot-password" className="text-brand-600 hover:underline">
            Send a new one
          </Link>
        </p>
      </div>
    </div>
  );
}
