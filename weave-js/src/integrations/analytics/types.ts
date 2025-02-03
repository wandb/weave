/**
 * Copied over from frontend/apps/service/analytics. Should be kept in sync with the original.
 *
 */
export enum ActivationMethods {
  MouseClick = 'mouse-click',
  KeyboardHotkey = 'keyboard-hotkey',
}

export type NoEventData = 'noeventdata';

/**
 * the event data has to be `Record<string, unknown>` because `Record<string, any>` unintentionally lets through arrays, and Segment will not ingest a list as `properties`.
 */
export type EventData = Record<string, unknown>;

export type Annotate<T extends EventData> = {
  [Property in keyof T]: {
    description: string;
    exampleValues: Array<T[Property]>;
  };
};

//
/**
 * These leading underscores are necessary to avoid collisions.
 * `makeTrackEvent` intersects Annotate<T> and EventMetadata, so an event property like `location` will collide with the `location` property on EventMetadata
 * e.g.
 * `{ location: { description: "...", exampleValues: ["", ""] }`, and
 * `{ description: string; location: string; motivation: string; }`
 */
export type EventMetadata = {
  _description: string; // a non-technical (if possible) description of the event,
  _location: string; // where in the app this event is fired from, if possible indicate specific positions and/or paths
  _motivation: string; // why we are collecting this data
};
