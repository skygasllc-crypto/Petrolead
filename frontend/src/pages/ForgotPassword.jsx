import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import Logo from "../components/Logo";
import ErrorBanner from "../components/ErrorBanner";

const inputClasses =
  "w-full rounded-md border border-base-600 bg-base-800 px-3 py-2 text-sm text-ink-100 focus:border-brand-500 focus:outline-none";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.forgotPassword(email);
      setSent(true);
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
          <h1 className="text-lg font-semibold text-ink-100">Reset your password</h1>
          {sent ? (
            <p className="mt-3 text-sm text-ink-500">
              If an account exists for <span className="text-ink-100">{email}</span>, we&apos;ve
              emailed it a link to choose a new password. The link expires in an hour. No email
              after a few minutes? Check your spam folder, or contact support and we can send you
              a link directly.
            </p>
          ) : (
            <>
              <p className="mt-1 text-sm text-ink-500">
                Enter the email you signed up with and we&apos;ll send you a reset link.
              </p>
              <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs font-medium uppercase tracking-wide text-ink-700">
                    Email
                  </span>
                  <input
                    type="email"
                    required
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={inputClasses}
                    placeholder="you@company.com"
                  />
                </label>

                {error && <ErrorBanner message={error} />}

                <button
                  type="submit"
                  disabled={submitting}
                  className="mt-2 inline-flex items-center justify-center rounded-md bg-brand-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Sending..." : "Send Reset Link"}
                </button>
              </form>
            </>
          )}
        </div>
        <p className="mt-4 text-center text-sm text-ink-500">
          Remembered it?{" "}
          <Link to="/login" className="text-brand-600 hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
