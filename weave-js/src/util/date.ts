/**
 * Date utility functions for parsing and formatting dates
 */

import moment from 'moment';

/**
 * Attempts to parse a date string into a Date object
 * Handles common date formats and basic relative dates
 *
 * @param dateStr The date string to parse
 * @returns A Date object if parsing was successful, or null if parsing failed
 */
export const parseDate = (dateStr: string): Date | null => {
  if (!dateStr || !dateStr.trim()) {
    return null;
  }

  const now = new Date();
  const trimmedStr = dateStr.trim();
  const lowerStr = trimmedStr.toLowerCase();

  // Handle last/next day of the week
  const lastNextDayOfWeekPattern =
    /^(last|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)$/i;
  const lastNextDayOfWeekMatch = lowerStr.match(lastNextDayOfWeekPattern);
  if (lastNextDayOfWeekMatch) {
    const direction = lastNextDayOfWeekMatch[1].toLowerCase();
    const targetDay = lastNextDayOfWeekMatch[2].toLowerCase();

    // Get current day of week (0 = Sunday, 1 = Monday, etc.)
    const currentDay = now.getDay();

    // Get target day index (0 = Sunday, 1 = Monday, etc.)
    const targetDayIndex = [
      'sunday',
      'monday',
      'tuesday',
      'wednesday',
      'thursday',
      'friday',
      'saturday',
    ].indexOf(targetDay);

    if (targetDayIndex !== -1) {
      // Calculate days to add/subtract
      let daysToAdd = targetDayIndex - currentDay;
      if (direction === 'last') {
        // For 'last', if target day is after current day, we need to go back 2 weeks
        if (daysToAdd > 0) {
          daysToAdd -= 7;
        }
      } else {
        // For 'next', if target day is before current day, we need to go forward 2 weeks
        if (daysToAdd < 0) {
          daysToAdd += 7;
        }
      }
      const result = new Date(now);
      result.setDate(result.getDate() + daysToAdd);
      return result;
    }
  }

  // Handle shorthand relative dates (e.g., "1d", "2w", "3mo", "1y", "4h", "30m", "10s")
  const shorthandPattern = /^(\d+)([dwymoh]|mo|s)$/i;
  const shorthandMatch = trimmedStr.match(shorthandPattern);
  if (shorthandMatch) {
    const amount = parseInt(shorthandMatch[1], 10);
    const unit = shorthandMatch[2].toLowerCase();
    const result = new Date(now);

    switch (unit) {
      case 'd':
        result.setDate(result.getDate() - amount);
        result.setHours(0, 0, 0, 0);
        return result;
      case 'w':
        result.setDate(result.getDate() - amount * 7);
        result.setHours(0, 0, 0, 0);
        return result;
      case 'mo':
        result.setMonth(result.getMonth() - amount);
        result.setHours(0, 0, 0, 0);
        return result;
      case 'm':
        result.setMinutes(result.getMinutes() - amount);
        return result;
      case 'h':
        result.setHours(result.getHours() - amount);
        result.setMinutes(0, 0, 0);
        return result;
      case 'y':
        result.setFullYear(result.getFullYear() - amount);
        result.setHours(0, 0, 0, 0);
        return result;
      case 's':
        result.setSeconds(result.getSeconds() - amount);
        return result;
    }
  }

  // Handle basic natural language dates
  if (lowerStr === 'today') {
    return new Date(now.setHours(0, 0, 0, 0));
  } else if (lowerStr === 'yesterday') {
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    yesterday.setHours(0, 0, 0, 0);
    return yesterday;
  } else if (lowerStr === 'tomorrow') {
    const tomorrow = new Date(now);
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(0, 0, 0, 0);
    return tomorrow;
  } else if (lowerStr === 'now' || lowerStr === 'current time') {
    return new Date(now);
  }

  const units = 'minute|hour|day|week|month|year|second';

  // Handle "X minutes/hours/days/weeks/months/years ago"
  const agoPattern = new RegExp(`^(\\d+)\\s+(${units})s?\\s+ago$`, 'i');
  const agoMatch = lowerStr.match(agoPattern);
  if (agoMatch) {
    const amount = parseInt(agoMatch[1], 10);
    const unit = agoMatch[2].toLowerCase();
    const result = new Date(now);

    switch (unit) {
      case 'minute':
        result.setMinutes(result.getMinutes() - amount);
        return result;
      case 'hour':
        result.setHours(result.getHours() - amount);
        return result;
      case 'day':
        result.setDate(result.getDate() - amount);
        return result;
      case 'week':
        result.setDate(result.getDate() - amount * 7);
        return result;
      case 'month':
        result.setMonth(result.getMonth() - amount);
        return result;
      case 'year':
        result.setFullYear(result.getFullYear() - amount);
        return result;
    }
  }

  // Handle "in X days/weeks/months/years"
  const inFuturePattern = new RegExp(`^in\\s+(\\d+)\\s+(${units})s?$`, 'i');
  const inFutureMatch = lowerStr.match(inFuturePattern);
  if (inFutureMatch) {
    const amount = parseInt(inFutureMatch[1], 10);
    const unit = inFutureMatch[2].toLowerCase();
    const result = new Date(now);

    switch (unit) {
      case 'minute':
        result.setMinutes(result.getMinutes() + amount);
        return result;
      case 'hour':
        result.setHours(result.getHours() + amount);
        return result;
      case 'day':
        result.setDate(result.getDate() + amount);
        return result;
      case 'week':
        result.setDate(result.getDate() + amount * 7);
        return result;
      case 'month':
        result.setMonth(result.getMonth() + amount);
        return result;
      case 'year':
        result.setFullYear(result.getFullYear() + amount);
        return result;
    }
  }

  // Handle last/next for basic time units
  const lastNextPattern = new RegExp(`^(last|next)\\s+(${units})$`, 'i');
  const lastNextMatch = lowerStr.match(lastNextPattern);
  if (lastNextMatch) {
    const direction = lastNextMatch[1].toLowerCase();
    const unit = lastNextMatch[2].toLowerCase();
    const multiplier = direction === 'last' ? -1 : 1;
    const result = new Date(now);

    switch (unit) {
      case 'minute':
        result.setMinutes(result.getMinutes() + multiplier);
        return result;
      case 'hour':
        result.setHours(result.getHours() + multiplier);
        return result;
      case 'day':
        result.setDate(result.getDate() + multiplier);
        return result;
      case 'week':
        result.setDate(result.getDate() + multiplier * 7);
        return result;
      case 'month':
        result.setMonth(result.getMonth() + multiplier);
        return result;
      case 'year':
        result.setFullYear(result.getFullYear() + multiplier);
        return result;
    }
  }

  // Try parsing with moment for standard date formats
  const momentDate = moment(trimmedStr);
  if (momentDate.isValid()) {
    // Check if the date is within a year from now
    const oneYearFromNow = moment().add(1, 'year');
    const oneYearAgo = moment().subtract(1, 'year');

    if (momentDate.isBetween(oneYearAgo, oneYearFromNow, 'day', '[]')) {
      return momentDate.toDate();
    }
  }

  // If all parsing attempts fail, return null
  return null;
};

/**
 * Determines if a date input string represents a relative date
 *
 * @param value The date string to check
 * @returns True if the input represents a relative date, false otherwise
 */
export const isRelativeDate = (value: string): boolean => {
  if (!value || typeof value !== 'string') {
    return false;
  }

  const trimmedValue = value.trim().toLowerCase();

  // Check for shorthand patterns (e.g., "1d", "2w", "3mo", "5h", "10m")
  if (/^\d+([dwymoh]|mo)$/i.test(trimmedValue)) {
    return true;
  }

  // Check for natural language relative terms
  const relativeKeywords = [
    'ago',
    'last',
    'next',
    'this',
    'yesterday',
    'today',
    'tomorrow',
    'in',
  ];

  return relativeKeywords.some(keyword => trimmedValue.includes(keyword));
};

/**
 * Formats a date as a string with the specified format
 *
 * @param date The date to format
 * @param format The format string (defaults to 'YYYY-MM-DD HH:mm:ss')
 * @returns A formatted date string, or empty string if date is invalid
 */
export const formatDate = (
  date: Date | null | undefined,
  format = 'YYYY-MM-DD HH:mm:ss'
): string => {
  if (!date) {
    return '';
  }
  return moment(date).local().format(format);
};

/**
 * Formats a date as just the date (without time)
 *
 * @param date The date to format
 * @param format The format string (defaults to 'YYYY-MM-DD')
 * @returns A formatted date string, or empty string if date is invalid
 */
export const formatDateOnly = (
  date: Date | null | undefined,
  format = 'YYYY-MM-DD'
): string => {
  if (!date) {
    return '';
  }
  return moment(date).local().format(format);
};
