import { Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import ScrollManager from "./components/ScrollManager";
import Layout from "./components/Layout";
import Landing from "./pages/Landing";
import LinkedInEmailFinder from "./pages/LinkedInEmailFinder";
import CompanySearch from "./pages/CompanySearch";
import EmailExtractor from "./pages/EmailExtractor";
import EmailVerifierProduct from "./pages/EmailVerifierProduct";
import Pricing from "./pages/Pricing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Dashboard from "./pages/Dashboard";
import Discover from "./pages/Discover";
import EmailFinder from "./pages/EmailFinder";
import EmailVerifier from "./pages/EmailVerifier";
import Companies from "./pages/Companies";
import CompanyProfile from "./pages/CompanyProfile";
import Emails from "./pages/Emails";
import SearchHistory from "./pages/SearchHistory";
import ScheduledSearches from "./pages/ScheduledSearches";
import Settings from "./pages/Settings";
import AdminUsers from "./pages/AdminUsers";
import Billing from "./pages/Billing";

export default function App() {
  return (
    <AuthProvider>
      <ScrollManager />
      <Routes>
        {/* Public marketing pages */}
        <Route path="/" element={<Landing />} />
        <Route path="/company-search" element={<CompanySearch />} />
        <Route path="/linkedin-email-finder" element={<LinkedInEmailFinder />} />
        <Route path="/email-extractor" element={<EmailExtractor />} />
        <Route path="/email-verifier" element={<EmailVerifierProduct />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/discover" element={<Discover />} />
            <Route path="/email-finder" element={<EmailFinder />} />
            <Route path="/verify-emails" element={<EmailVerifier />} />
            <Route path="/companies" element={<Companies />} />
            <Route path="/companies/:id" element={<CompanyProfile />} />
            <Route path="/emails" element={<Emails />} />
            <Route path="/searches" element={<SearchHistory />} />
            <Route path="/scheduled" element={<ScheduledSearches />} />
            <Route path="/billing" element={<Billing />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/admin/users" element={<AdminUsers />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
