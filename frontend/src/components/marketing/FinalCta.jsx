import { Link } from "react-router-dom";
import Icon from "./Icon";
import { useAuth } from "../../context/AuthContext";

export default function FinalCta({ title, points, appPath = "/dashboard" }) {
  const { user } = useAuth();
  return (
    <section className="bg-base-850 px-4 pb-20 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl rounded-3xl bg-gradient-to-br from-brand-500 to-brand-700 px-6 py-16 text-center sm:px-12">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">{title}</h2>
        <ul className="mt-6 flex flex-col items-center justify-center gap-3 text-sm text-brand-100 sm:flex-row sm:gap-8">
          {points.map((t) => (
            <li key={t} className="flex items-center gap-2">
              <Icon name="check" className="h-4 w-4" />
              {t}
            </li>
          ))}
        </ul>
        <Link
          to={user ? appPath : "/register"}
          className="mt-10 inline-flex items-center justify-center rounded-md bg-white px-7 py-3.5 text-base font-semibold text-brand-700 shadow-sm hover:bg-brand-50"
        >
          {user ? "Open PetroLead" : "Create your account"}
        </Link>
      </div>
    </section>
  );
}
