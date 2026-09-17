import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/* Per-page title, description and canonical URL.

   This is a single-page app: without this every route would share one title
   and one description, which is what search engines index and what shows up
   as the clickable line in results. Mounted once, it rewrites the tags on
   each navigation instead of every page having to remember to.

   Anything not listed below — the signed-in app, sign-in, sign-up, admin —
   is marked noindex. robots.txt asks crawlers not to fetch those; the meta
   tag is what keeps them out of the index if something links to one
   directly. */

export const SITE_URL = "https://petrolead.org";

const DEFAULT_TITLE = "PetroLead — Energy B2B Leads & Verified Emails";
const DEFAULT_DESCRIPTION =
  "Find petroleum and energy companies and get verified business emails for their decision-makers.";

const PAGES = {
  "/": {
    title: DEFAULT_TITLE,
    description:
      "Find petroleum and energy companies worldwide and get verified business emails for their decision-makers. Search by country, product and activity.",
  },
  "/company-search": {
    title: "Company Search — Find Energy & Petroleum Companies | PetroLead",
    description:
      "Search for petroleum, oil, gas and energy companies by country, city, product and activity, then save the ones worth contacting.",
  },
  "/linkedin-email-finder": {
    title: "LinkedIn Email Finder — Get Business Emails | PetroLead",
    description:
      "Paste a LinkedIn profile link, or a name and company, and get that person's business email address. Only pay a credit when an email is found.",
  },
  "/email-extractor": {
    title: "Email Extractor — Pull Contacts From Any Website | PetroLead",
    description:
      "Extract business emails, phone numbers and social profiles from a company's own website. Included in every plan, no credits used.",
  },
  "/email-verifier": {
    title: "Email Verifier — Check Business Emails | PetroLead",
    description:
      "Check whether a business email address is worth sending to before you send. No credits used, and we never email the address to test it.",
  },
  "/pricing": {
    title: "Pricing — Plans From $20 a Month | PetroLead",
    description:
      "Simple monthly plans with email credits that roll over. Pay in Bitcoin, USDT (TRC-20) or TRX. Save 25% on yearly billing.",
  },
  "/terms": {
    title: "Terms of Service | PetroLead",
    description: "The terms that govern your use of PetroLead.",
  },
  "/privacy": {
    title: "Privacy Policy | PetroLead",
    description:
      "What PetroLead collects, why, and how to ask us to change or delete it — whether or not you are a customer.",
  },
};

/** Create the tag if it isn't there yet, then set its content. */
function upsertMeta(attribute, name, content) {
  let tag = document.head.querySelector(`meta[${attribute}="${name}"]`);
  if (!tag) {
    tag = document.createElement("meta");
    tag.setAttribute(attribute, name);
    document.head.appendChild(tag);
  }
  tag.setAttribute("content", content);
}

function upsertCanonical(href) {
  let link = document.head.querySelector('link[rel="canonical"]');
  if (!link) {
    link = document.createElement("link");
    link.setAttribute("rel", "canonical");
    document.head.appendChild(link);
  }
  link.setAttribute("href", href);
}

export default function Seo() {
  const { pathname } = useLocation();

  useEffect(() => {
    const page = PAGES[pathname];
    const title = page?.title ?? DEFAULT_TITLE;
    const description = page?.description ?? DEFAULT_DESCRIPTION;
    const canonical = `${SITE_URL}${pathname === "/" ? "/" : pathname}`;

    document.title = title;
    upsertMeta("name", "description", description);
    // Private pages stay out of the index even if something links to them.
    upsertMeta("name", "robots", page ? "index, follow" : "noindex, nofollow");

    upsertMeta("property", "og:title", title);
    upsertMeta("property", "og:description", description);
    upsertMeta("property", "og:url", canonical);
    upsertMeta("name", "twitter:title", title);
    upsertMeta("name", "twitter:description", description);

    // Only a public page should claim a canonical URL; pointing one at a
    // signed-in route would invite crawlers to index it.
    if (page) {
      upsertCanonical(canonical);
    } else {
      document.head.querySelector('link[rel="canonical"]')?.remove();
    }
  }, [pathname]);

  return null;
}
