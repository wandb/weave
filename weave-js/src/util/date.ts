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

  // Trim the input
  const trimmedStr = dateStr.trim();
  if (!trimmedStr) {
    return null;
  }

  // Try parsing with moment
  const momentDate = moment(trimmedStr);
  if (momentDate.isValid()) {
    return momentDate.toDate();
  }

  // Try parsing natural language dates
  const lowerStr = trimmedStr.toLowerCase();
  const now = new Date();

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
  const lastNextPattern = /^(last|next)\s+(day|week|month|year)$/i;
  const lastNextMatch = lowerStr.match(lastNextPattern);
  if (lastNextMatch) {
    const direction = lastNextMatch[1].toLowerCase();
    const unit = lastNextMatch[2].toLowerCase();
    const multiplier = direction === 'last' ? -1 : 1;

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

  // If all parsing attempts fail, return null
  return null;
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
