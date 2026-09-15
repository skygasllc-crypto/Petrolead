import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "../api/client";

const BillingContext = createContext(null);

/** The signed-in user's plan and credit balance, shared across the app so
 * the header badge updates after a lookup spends credits. */
export function BillingProvider({ children }) {
  const [billing, setBilling] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setBilling(await api.billingMe());
    } catch {
      // Keep the last known state — a failed refresh shouldn't blank the header.
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <BillingContext.Provider value={{ billing, refresh }}>{children}</BillingContext.Provider>
  );
}

export function useBilling() {
  const ctx = useContext(BillingContext);
  if (!ctx) throw new Error("useBilling must be used within a BillingProvider");
  return ctx;
}
