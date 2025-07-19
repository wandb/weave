/**
 * Constants used throughout the magician library.
 */

/** Default model to use when no model is selected */
export const DEFAULT_MODEL = 'coreweave/moonshotai/Kimi-K2-Instruct';

/** Default width of the magic tooltip in pixels */
export const DEFAULT_TOOLTIP_WIDTH = 350;

/** Default number of lines for the textarea in the tooltip */
export const DEFAULT_TEXTAREA_LINES = 7;

/** Approximate line height in pixels for calculating textarea height */
export const LINE_HEIGHT_PX = 24;

/** Delay in milliseconds before focusing the textarea after opening */
export const TEXTAREA_FOCUS_DELAY_MS = 100;

/** Delay in milliseconds before resetting state after closing tooltip */
export const STATE_RESET_DELAY_MS = 500;

/** Default placeholder text for revision input */
export const DEFAULT_REVISION_PLACEHOLDER = 'What would you like to change?';

/** Default temperature for LLM completions */
export const DEFAULT_TEMPERATURE = 0.7;
