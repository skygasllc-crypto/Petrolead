/** A `?next=` path that's safe to redirect to after login or sign-up —
 * only paths within this app, never another site. */
export function safeNextPath(value) {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : null;
}
