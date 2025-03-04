import {
  MOON_250,
  TEAL_350,
  TEAL_400,
} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useEffect, useRef, useState} from 'react';

import {
  dateToISOString,
  formatDate,
  formatDateOnly,
  isRelativeDate,
  parseDate,
} from '../../../../../util/date';

type PredefinedSuggestion = {
  abbreviation: string;
  label: string;
};

const PREDEFINED_SUGGESTIONS: PredefinedSuggestion[] = [
  {abbreviation: '1d', label: '1 day'},
  {abbreviation: '2d', label: '2 days'},
  {abbreviation: '1w', label: '1 week'},
  {abbreviation: '2w', label: '2 weeks'},
  {abbreviation: '1m', label: '1 month'},
];

type SelectDatetimeDropdownProps = {
  value: string;
  onChange: (value: string) => void;
};

export const SelectDatetimeDropdown: React.FC<SelectDatetimeDropdownProps> = ({
  value,
  onChange,
}) => {
  // This is the display value shown in the input (e.g., "3d", "2w", etc.)
  const [inputValue, setInputValue] = useState(value || '');
  // This is the parsed date object
  const [parsedDate, setParsedDate] = useState<Date | null>(null);
  const [isDropdownVisible, setDropdownVisible] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(
    null
  );
  const [isInputHovered, setIsInputHovered] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);

  // Initialize the parsed date from the initial value
  useEffect(() => {
    if (value) {
      const date = parseDate(value);
      setParsedDate(date);
    }
  }, [value]);

  // Compute yesterday's date string (date only, no time)
  const yesterdayDate = new Date();
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  const yesterdayString = formatDateOnly(yesterdayDate);

  // Predefined suggestions with a nicename for each
  const yesterdaySuggestion: PredefinedSuggestion = {
    abbreviation: yesterdayString,
    label: 'Yesterday (Absolute)',
  };
  const predefinedSuggestions: PredefinedSuggestion[] = [
    ...PREDEFINED_SUGGESTIONS,
    yesterdaySuggestion,
  ];

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newInputValue = event.target.value;
    setInputValue(newInputValue);

    // Parse the input to get a date
    const date = parseDate(newInputValue);
    setParsedDate(date);

    // Call the parent onChange handler with the timestamp
    if (date) {
      onChange(dateToISOString(date));
    } else {
      // If we couldn't parse a date, pass the raw input
      // This allows for storing relative date strings like "3d" directly
      onChange(newInputValue);
    }

    // Check against our predefined suggestions by their value
    const isPredefined = predefinedSuggestions.some(
      s => s.abbreviation === newInputValue
    );
    if (!isPredefined) {
      setSelectedSuggestion(null);
    }
  };

  const handleFocus = () => {
    setDropdownVisible(true);
    setIsInputFocused(true);
  };

  const handleBlur = (event: React.FocusEvent<HTMLInputElement>) => {
    if (
      dropdownRef.current &&
      !dropdownRef.current.contains(event.relatedTarget as Node)
    ) {
      setDropdownVisible(false);
    }
    setIsInputFocused(false);
  };

  const handleSuggestionClick = (suggestionValue: string) => {
    setInputValue(suggestionValue);

    // Parse the suggestion to get a date
    const date = parseDate(suggestionValue);
    setParsedDate(date);

    // Call the parent onChange handler with the timestamp
    if (date) {
      onChange(dateToISOString(date));
    } else {
      // If we couldn't parse a date, pass the raw input
      onChange(suggestionValue);
    }

    setSelectedSuggestion(suggestionValue);
    setDropdownVisible(false);
    if (inputRef.current) {
      inputRef.current.blur();
    }
  };

  const handleMouseEnter = (index: number) => {
    setHoveredIndex(index);
  };

  const handleMouseLeave = () => {
    setHoveredIndex(null);
  };

  const handleInputMouseEnter = () => {
    setIsInputHovered(true);
  };

  const handleInputMouseLeave = () => {
    setIsInputHovered(false);
  };

  // Compute a label for the input based on the input text and parse result
  const dateLabel = inputValue.trim()
    ? parsedDate
      ? isRelativeDate(inputValue)
        ? 'Relative'
        : 'Absolute'
      : 'Unparsable'
    : '';

  // Optionally, set a color for the label
  const labelColor = !inputValue.trim()
    ? '#000'
    : parsedDate
    ? isRelativeDate(inputValue)
      ? '#4CAF50' // green for relative
      : '#2196F3' // blue for absolute
    : '#F44336'; // red for unparsable

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        marginBottom: '5px',
      }}>
      <Icon
        name="date"
        style={{
          position: 'absolute',
          top: '50%',
          left: '9px',
          transform: 'translateY(-50%)',
          fontSize: '16px',
        }}
      />
      <input
        type="text"
        value={inputValue}
        onChange={handleInputChange}
        onFocus={handleFocus}
        onBlur={handleBlur}
        onMouseEnter={handleInputMouseEnter}
        onMouseLeave={handleInputMouseLeave}
        placeholder="Enter a date..."
        style={{
          padding: '4px 12px', // Medium size padding
          paddingLeft: '32px',
          paddingRight: '80px', // extra space for the label on the right
          borderRadius: '4px',
          border: 0,
          boxShadow: isInputFocused
            ? `0 0 0 2px ${TEAL_400}`
            : isInputHovered
            ? `0 0 0 2px ${TEAL_350}`
            : `inset 0 0 0 1px ${MOON_250}`,
          outline: 'none',
          flex: 1,
          height: '32px',
          minHeight: '32px',
          boxSizing: 'border-box',
          fontSize: '16px',
          lineHeight: '24px',
          cursor: 'default',
        }}
        ref={inputRef}
      />
      {/* Date type label with a tooltip showing the parsed date */}
      {inputValue.trim() && (
        <span
          title={parsedDate ? `Parsed Date: ${formatDate(parsedDate)}` : ''}
          style={{
            position: 'absolute',
            right: '10px',
            top: '50%',
            transform: 'translateY(-50%)',
            fontSize: '12px',
            color: labelColor,
            cursor: parsedDate ? 'default' : 'help',
            zIndex: 2, // Ensure the label sits on top of the input
            pointerEvents: 'auto', // Make sure the label can receive pointer events
          }}>
          {dateLabel}
        </span>
      )}
      {isDropdownVisible && (
        <ul
          ref={dropdownRef}
          style={{
            position: 'absolute',
            top: '100%',
            left: '0',
            right: '0',
            backgroundColor: '#fff',
            border: '1px solid #ccc',
            borderRadius: '4px',
            marginTop: '4px',
            listStyle: 'none',
            fontSize: '14px',
            padding: '0',
            overflow: 'hidden',
            zIndex: 1000,
          }}>
          {parsedDate && (
            <li
              style={{
                padding: '8px',
                borderBottom: '1px solid #eee',
                color: '#555',
                cursor: 'default',
              }}>
              {/* Dynamic label for relative or absolute */}
              <strong>
                {isRelativeDate(inputValue) ? 'Relative:' : 'Absolute:'}
              </strong>{' '}
              {formatDate(parsedDate)}
            </li>
          )}
          {predefinedSuggestions.map((suggestion, index) => (
            <li
              key={index}
              onClick={() => handleSuggestionClick(suggestion.abbreviation)}
              onMouseEnter={() => handleMouseEnter(index)}
              onMouseLeave={handleMouseLeave}
              style={{
                padding: '8px',
                cursor: 'pointer',
                backgroundColor:
                  selectedSuggestion === suggestion.abbreviation
                    ? hoveredIndex === index
                      ? '#f8f8f8'
                      : '#E1F7FA'
                    : hoveredIndex === index
                    ? '#f8f8f8'
                    : '#fff',
              }}
              onMouseDown={e => e.preventDefault()}>
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}>
                <span>{suggestion.abbreviation}</span>
                <span style={{color: '#999'}}>{suggestion.label}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
