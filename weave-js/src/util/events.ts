/**
 * TODO: Connect to router.
 */
export function trackPage(properties: object, options: object) {
  (window.analytics as any).page?.(properties, options);
}
