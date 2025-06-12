/**
 * TODO: Duplicating required functions from app/src/util/date/
 *       It would be preferable to migrate the entire functionality into
 *       a shared location but there are problems with things like Jest
 *       version differences that I don't want to debug right now.
 */

/**
 * returns true if the first date is after the second one
 */
export function isAfter(date1: Date, date2: Date): boolean {
  return date1 > date2;
}

const NUM_MILLISECONDS_IN_SECOND = 1000;
export const NUM_SECONDS_IN_MINUTE = 60;
const NUM_MINUTES_IN_HOUR = 60;
export const NUM_SECONDS_IN_HOUR = NUM_SECONDS_IN_MINUTE * NUM_MINUTES_IN_HOUR;
const NUM_HOURS_IN_DAY = 24;
export const NUM_SECONDS_IN_DAY = NUM_HOURS_IN_DAY * NUM_SECONDS_IN_HOUR;
export const NUM_MILLISECONDS_IN_DAY =
  NUM_SECONDS_IN_DAY * NUM_MILLISECONDS_IN_SECOND;
export const NUM_DAYS_IN_WEEK = 7;
const NUM_CALENDAR_DAYS_IN_YEAR = 365; // not exact - inaccurate for leap years
export const APPROX_NUM_DAYS_IN_MONTH = 30;
export const APPROX_NUM_MILLISECONDS_IN_NON_LEAP_YEAR =
  NUM_CALENDAR_DAYS_IN_YEAR * NUM_MILLISECONDS_IN_DAY; // not astronomically correct

export function startOfDayUTC(date: Date): Date {
  const newDate = new Date(date);
  newDate.setUTCHours(0, 0, 0, 0);
  return newDate;
}

export function differenceInDaysExact(date1: Date, date2: Date) {
  return (date1.getTime() - date2.getTime()) / NUM_MILLISECONDS_IN_DAY;
}

/**
 * Returns the number of 24 hour cycles between the two dates. aka the number of days in UTC between
 * the two dates.
 *
 * NOTE: This differs from date-fns which doesn't count the number of 24 hour periods, but rather
 * the number of cycles to the "same local time next day" which may be more or less than 24 hours
 * with daylight savings.
 */
export function differenceInDays(date1: Date, date2: Date): number {
  return Math.trunc(differenceInDaysExact(date1, date2)); // trunc to ensure it'll be a whole number
}

// Get the number of calendar days between the given dates in UTC. This means that the times are removed from the dates and then the difference in days is calculated.
export function differenceInCalendarDaysUTC(date1: Date, date2: Date): number {
  const date1WithoutTime = startOfDayUTC(date1);
  const date2WithoutTime = startOfDayUTC(date2);
  return differenceInDays(date1WithoutTime, date2WithoutTime);
}
