import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

// React Router doesn't scroll on navigation: jump to the top of each new
// page, or to the `#section` a link points at (e.g. "/#faq" from another
// page). Moving to a new page jumps instantly — the stylesheet's smooth
// scrolling is only for moving around within the same page.
export default function ScrollManager() {
  const { pathname, hash } = useLocation();
  const previousPathname = useRef(pathname);

  useEffect(() => {
    const samePage = previousPathname.current === pathname;
    previousPathname.current = pathname;
    const behavior = samePage ? "smooth" : "instant";

    if (hash) {
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior });
    } else {
      window.scrollTo({ top: 0, behavior });
    }
  }, [pathname, hash]);

  return null;
}
