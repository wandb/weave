/**
 * Copied over from service.analytics. Should be kept in sync with the original.
 *
 */
import {Analytics} from './Analytics';
import {Annotate, EventData, EventMetadata, NoEventData} from './types';

export type EventConfig = {
  /* controls whether the event is sent */
  isEnabled?: boolean;
  /* controls how often the event is sent (0.0 - 1.0) */
  sampleRate?: number;
  /* logs the event data to the console */
  shouldLogToConsole?: boolean;
};

/**
 * Context for some of the quirks about the implementation here.
 *
 * The request from Data Science is for the following:
 * - to centralize the events for easier control / oversight through code file ownership
 * - to enforce a requirement that each eventData property have an annotated description for reference
 *
 * Design goals for engineering are:
 * - to provide a layer of insulation around the analytics library so that random errors don't occur when `window.analytics` is undefined
 * - to provide a layer of abstraction around the analytics library for easier maintenance / testing / refactoring
 * - to include some easy helpers for debugging
 * - to include some additional features such as sampling rates or disabling events
 *
 * Engineering and Data Science are both agreed that:
 * - we don't want annotation polluting either the JS bundle or the event data downstream
 *
 * Thus we have the unused second type variable of Annotate<T> here on this makeTrackEvent fn. This allows us to define a base type<T> for the properties that are required for each event, and to use it to power type checking when the track event function is called and provided data from the call site. Annotate<T> inspects the keys of T and creates a new type with the same keys, but with the suffix "Description" appended to each key. Requiring it as the second type argument for `makeTrackEvent` enforces the requirement that each property have a description. We ignore it in eslint because it's a meta-level requirement, and not a function level one.
 */

type EventDescription<T extends EventData | NoEventData> = T extends EventData
  ? Annotate<T> & EventMetadata
  : EventMetadata;

export const makeTrackEvent = <
  T extends EventData | NoEventData,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  D extends EventDescription<T>
>(
  eventName: string,
  config: Partial<EventConfig> = {},
  random: number = Math.random()
) => {
  const {isEnabled = true, sampleRate = 1, shouldLogToConsole = false} = config;

  const shouldTrack = isEnabled && random <= sampleRate;

  // `[undefined?]` makes the eventData parameter optional.
  // So the expected behavior is: for makeTrackEvent<NoEventData>, the
  // eventData parameter is optional, and for all other types the
  // parameter is required.
  return (...eventData: T extends NoEventData ? [undefined?] : [T]) => {
    if (shouldLogToConsole) {
      console.log(`[${eventName}]`, eventData);
    }

    if (shouldTrack) {
      // note that the type guarantees array of length 1
      Analytics.track(eventName as unknown as string, eventData[0] ?? {});
    }
  };
};
