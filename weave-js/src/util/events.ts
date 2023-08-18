/**
 * TODO: Connect to router.
 */
export function trackPage(properties: object, options: object) {
  window.analytics?.page?.(properties, options);
}
