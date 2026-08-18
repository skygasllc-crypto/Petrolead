import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Discover from "./pages/Discover";
import Companies from "./pages/Companies";
import CompanyProfile from "./pages/CompanyProfile";
import SearchHistory from "./pages/SearchHistory";
import ScheduledSearches from "./pages/ScheduledSearches";
import Settings from "./pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/discover" element={<Discover />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/companies/:id" element={<CompanyProfile />} />
        <Route path="/searches" element={<SearchHistory />} />
        <Route path="/scheduled" element={<ScheduledSearches />} />
        <Route path="/settings" element={<Settings />} />
      </Route>
    </Routes>
  );
}
