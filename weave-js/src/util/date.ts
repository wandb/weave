/**
 * Date utility functions for parsing and formatting dates
 */

import moment from 'moment';

/**
 * Attempts to parse a date string into a Date object
 * Handles various date formats and natural language
 *
 * @param dateStr The date string to parse
 * @returns A Date object if parsing was successful, or null if parsing failed
 */
export const parseDate = (dateStr: string): Date | null => {
  if (!dateStr || typeof dateStr !== 'string') {
    return null;
  }

  const now = new Date();

  // Trim the input
  const trimmedStr = dateStr.trim();
  if (!trimmedStr) {
    return null;
  }

  // Handle shorthand relative dates (e.g., "1d", "2w", "3m", "1y")
  const shorthandPattern = /^(\d+)([dwmy])$/i;
  const shorthandMatch = trimmedStr.match(shorthandPattern);
  if (shorthandMatch) {
    const amount = parseInt(shorthandMatch[1], 10);
    const unit = shorthandMatch[2].toLowerCase();

    switch (unit) {
      case 'd':
        const daysAgo = new Date(now);
        daysAgo.setDate(daysAgo.getDate() - amount);
        return daysAgo;
      case 'w':
        const weeksAgo = new Date(now);
        weeksAgo.setDate(weeksAgo.getDate() - amount * 7);
        return weeksAgo;
      case 'm':
        const monthsAgo = new Date(now);
        monthsAgo.setMonth(monthsAgo.getMonth() - amount);
        return monthsAgo;
      case 'y':
        const yearsAgo = new Date(now);
        yearsAgo.setFullYear(yearsAgo.getFullYear() - amount);
        return yearsAgo;
    }
  }

  // Try parsing with moment
  const momentDate = moment(trimmedStr);
  if (momentDate.isValid()) {
    return momentDate.toDate();
  }

  // Try parsing natural language dates
  const lowerStr = trimmedStr.toLowerCase();

  // Handle "today", "yesterday", "tomorrow"
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
  }

  // Handle "last week", "next month", etc.
  const lastNextPattern =
    /^(last|next|this)\s+(day|week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)$/i;
  const lastNextMatch = lowerStr.match(lastNextPattern);
  if (lastNextMatch) {
    const direction = lastNextMatch[1].toLowerCase();
    const unit = lastNextMatch[2].toLowerCase();

    // Handle days of the week
    const daysOfWeek = [
      'sunday',
      'monday',
      'tuesday',
      'wednesday',
      'thursday',
      'friday',
      'saturday',
    ];
    if (daysOfWeek.includes(unit)) {
      const today = now.getDay();
      const targetDay = daysOfWeek.indexOf(unit);
      let daysToAdd = 0;

      if (direction === 'this') {
        // This week's day
        daysToAdd = (targetDay - today + 7) % 7;
        if (daysToAdd === 0 && today === targetDay) {
          daysToAdd = 0; // Today is the target day
        }
      } else if (direction === 'next') {
        // Next week's day
        daysToAdd = (targetDay - today + 7) % 7;
        if (daysToAdd === 0) {
          daysToAdd = 7; // Next week's same day
        }
      } else if (direction === 'last') {
        // Last week's day
        daysToAdd = (targetDay - today - 7) % 7;
        if (daysToAdd === 0 && today === targetDay) {
          daysToAdd = -7; // Last week's same day
        }
      }

      const res = new Date(now);
      res.setDate(res.getDate() + daysToAdd);
      return res;
    }

    // Handle other time units
    const multiplier = direction === 'last' ? -1 : direction === 'next' ? 1 : 0;

    const result = new Date(now);
    switch (unit) {
      case 'day':
        result.setDate(result.getDate() + multiplier);
        break;
      case 'week':
        result.setDate(result.getDate() + multiplier * 7);
        break;
      case 'month':
        result.setMonth(result.getMonth() + multiplier);
        break;
      case 'year':
        result.setFullYear(result.getFullYear() + multiplier);
        break;
    }
    return result;
  }

  // Handle "X days/weeks/months/years ago"
  const agoPattern = /^(\d+)\s+(day|week|month|year)s?\s+ago$/i;
  const agoMatch = lowerStr.match(agoPattern);
  if (agoMatch) {
    const amount = parseInt(agoMatch[1], 10);
    const unit = agoMatch[2].toLowerCase();

    const result = new Date(now);
    switch (unit) {
      case 'day':
        result.setDate(result.getDate() - amount);
        break;
      case 'week':
        result.setDate(result.getDate() - amount * 7);
        break;
      case 'month':
        result.setMonth(result.getMonth() - amount);
        break;
      case 'year':
        result.setFullYear(result.getFullYear() - amount);
        break;
    }
    return result;
  }

  // Handle "in X days/weeks/months/years"
  const inFuturePattern = /^in\s+(\d+)\s+(day|week|month|year)s?$/i;
  const inFutureMatch = lowerStr.match(inFuturePattern);
  if (inFutureMatch) {
    const amount = parseInt(inFutureMatch[1], 10);
    const unit = inFutureMatch[2].toLowerCase();

    const result = new Date(now);
    switch (unit) {
      case 'day':
        result.setDate(result.getDate() + amount);
        break;
      case 'week':
        result.setDate(result.getDate() + amount * 7);
        break;
      case 'month':
        result.setMonth(result.getMonth() + amount);
        break;
      case 'year':
        result.setFullYear(result.getFullYear() + amount);
        break;
    }
    return result;
  }

  // Handle quarter patterns like "Q1 2023", "2023 Q2", etc.
  const quarterPattern = /^(?:Q([1-4])\s+(\d{4})|(\d{4})\s+Q([1-4]))$/i;
  const quarterMatch = lowerStr.match(quarterPattern);
  if (quarterMatch) {
    const quarter = parseInt(quarterMatch[1] || quarterMatch[4], 10);
    const year = parseInt(quarterMatch[2] || quarterMatch[3], 10);
    const month = (quarter - 1) * 3; // Q1=0 (Jan), Q2=3 (Apr), Q3=6 (Jul), Q4=9 (Oct)

    return new Date(year, month, 1);
  }

  // Handle month and year patterns like "Jan 2023", "January 2023", "2023 Jan", etc.
  const monthNames = [
    'january',
    'february',
    'march',
    'april',
    'may',
    'june',
    'july',
    'august',
    'september',
    'october',
    'november',
    'december',
  ];
  const monthAbbreviations = [
    'jan',
    'feb',
    'mar',
    'apr',
    'may',
    'jun',
    'jul',
    'aug',
    'sep',
    'oct',
    'nov',
    'dec',
  ];

  // Try "Month YYYY" or "Mon YYYY" format
  for (let i = 0; i < monthNames.length; i++) {
    const fullPattern = new RegExp(`^${monthNames[i]}\\s+(\\d{4})$`, 'i');
    const abbrPattern = new RegExp(
      `^${monthAbbreviations[i]}\\s+(\\d{4})$`,
      'i'
    );

    const fullMatch = lowerStr.match(fullPattern);
    const abbrMatch = lowerStr.match(abbrPattern);

    if (fullMatch || abbrMatch) {
      const year = parseInt(fullMatch?.[1] || abbrMatch?.[1] || '0', 10);
      return new Date(year, i, 1);
    }
  }

  // Try "YYYY Month" or "YYYY Mon" format
  for (let i = 0; i < monthNames.length; i++) {
    const fullPattern = new RegExp(`^(\\d{4})\\s+${monthNames[i]}$`, 'i');
    const abbrPattern = new RegExp(
      `^(\\d{4})\\s+${monthAbbreviations[i]}$`,
      'i'
    );

    const fullMatch = lowerStr.match(fullPattern);
    const abbrMatch = lowerStr.match(abbrPattern);

    if (fullMatch || abbrMatch) {
      const year = parseInt(fullMatch?.[1] || abbrMatch?.[1] || '0', 10);
      return new Date(year, i, 1);
    }
  }

  // X days/weeks/months before/after today
  const beforeAfterPattern =
    /^(\d+)\s+(day|week|month|year)s?\s+(before|after)\s+today$/i;
  const beforeAfterMatch = lowerStr.match(beforeAfterPattern);
  if (beforeAfterMatch) {
    const amount = parseInt(beforeAfterMatch[1], 10);
    const unit = beforeAfterMatch[2].toLowerCase();
    const direction = beforeAfterMatch[3].toLowerCase();
    const multiplier = direction === 'before' ? -1 : 1;

    const result = new Date(now);
    switch (unit) {
      case 'day':
        result.setDate(result.getDate() + amount * multiplier);
        break;
      case 'week':
        result.setDate(result.getDate() + amount * 7 * multiplier);
        break;
      case 'month':
        result.setMonth(result.getMonth() + amount * multiplier);
        break;
      case 'year':
        result.setFullYear(result.getFullYear() + amount * multiplier);
        break;
    }
    return result;
  }

  // Handle "now", "right now", "current time"
  if (/^(now|right now|current time)$/i.test(lowerStr)) {
    return new Date(now);
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

  // Check for shorthand patterns (e.g., "1d", "2w")
  if (/^\d+[dwmy]$/i.test(trimmedValue)) {
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
    'previous',
    'past',
    'coming',
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
  return moment(date).format(format);
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
  return moment(date).format(format);
};

/**
 * Converts a date to ISO string or returns empty string if null
 *
 * @param date The date to convert
 * @returns ISO string representation of the date, or empty string if date is invalid
 */
export const dateToISOString = (date: Date | null | undefined): string => {
  return date ? date.toISOString() : '';
};
