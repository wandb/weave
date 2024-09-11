/**
 * Copied over from service.analytics. Should be kept in sync with the original.
 *
 */
import * as Sentry from '@sentry/react';

import {EventData} from './types';
/**
 * Previously `window.analytics.track` was assigned as a default for `track` arguments in function declarations so that the dependency on Segment could be easily injected (useful for things like testing), e.g.:
 * `const makeTracker = (track = window?.analytics?.track) => (name, data) => track(name,data)`
 *
 * However, the fn often runs with the initialization of the JS bundle, which is _before_ the deferred loading of Segment completes and overwrites the fn at `window.analytics.track`. So moving this to an easily mockable exported object. Thus we can easily overwrite it w/ mocks in tests, but the `track` call will still resolve its reference to Segment after initialiation
 */

export const Analytics = {
  /**
   * The underlying Segment typing is stupidly loose. It overloads the `track` fn and types `eventData` as `Object`. An `Object` in JS is an overly broad definition that bundles in Semantic confusion. They includes Dates, Arrays, Errors, etc... none of which should be allowed here. What we really want is `Record<string, SerializableValue>` but that's not a built-in thing and it's overkill. `unknown` works fine because we don't use these types anywhere downstream— we just send them off into the Segment void
   */
  track: (eventName: string, eventData: EventData) => {
    if (
      Array.isArray(eventData) || // Segment accepts lists but won't process them
      typeof eventData !== 'object' || // exclude the primitives
      eventData === null // typeof null => 'object' :grimace:
      // note this still leaves holes for Date / Error / any other weird "object" types
    ) {
      throw new Error('Analytics data must be a non-array object.');
    }

    let trackCall;
    let initialized;
    // optional chaining on the root level object doesn't work
    // window?.analytics?.track will THROW if window is undefined
    try {
      trackCall = (window as any).analytics.track;
      // @ts-ignore the `initialized` property is not in the type definition?
      initialized = window.analytics.initialized;
    } catch {
      trackCall = null;
      initialized = false;
    }

    // only hit Sentry in prod
    const envIsProd =
      (window as any)?.CONFIG?.ENVIRONMENT_NAME === 'production';
    const captureMessage = envIsProd ? Sentry.captureMessage : () => {};

    // these represent conditions where expected behavior will fail
    // known conditions are that `window.analytics.track` exists but the service is
    // not initialized so it points to a non-functional track fn
    // @ts-ignore the `initialized` property is not in the type definition?

    if (trackCall && initialized) {
      try {
        trackCall(eventName, eventData);
      } catch (err) {
        // this is probably an impossible edge case where Segment shows as initialized
        // but the tracking fn call is unvailable
        captureMessage(
          'Segment initialized, unknown error calling track function'
        );
      }
    } else if (trackCall && !initialized) {
      captureMessage('Segment not initialized, event is lost.');
    } else if (!trackCall) {
      captureMessage('Tracking event lost. Check Segment initialization.');
    }
  },
};
