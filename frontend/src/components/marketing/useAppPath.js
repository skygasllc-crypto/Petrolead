import { useAuth } from "../../context/AuthContext";

/** Where a marketing call-to-action goes: the app tool for logged-in
 * visitors, sign-up for everyone else. */
export default function useAppPath(appPath) {
  const { user } = useAuth();
  return user ? appPath : "/register";
}
