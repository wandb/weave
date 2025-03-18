import {
  MOON_150,
  MOON_250,
  TEAL_350,
  TEAL_400,
} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useEffect, useMemo, useRef, useState} from 'react';

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
  {abbreviation: '1d', label: '1 Day'},
  {abbreviation: '2d', label: '2 Days'},
  {abbreviation: '1w', label: '1 Week'},
  {abbreviation: '2w', label: '2 Weeks'},
  {abbreviation: '1m', label: '1 Month'},
];

type SelectDatetimeDropdownProps = {
  value: string;
  onChange: (value: string) => void;
};

export const SelectDatetimeDropdown: React.FC<SelectDatetimeDropdownProps> = ({
  value,
  onChange,
}) => {
  const [inputValue, setInputValue] = useState(value || '');
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
  const predefinedSuggestions: PredefinedSuggestion[] = useMemo(() => {
    const yesterdayDate = new Date();
    yesterdayDate.setDate(yesterdayDate.getDate() - 1);
    const yesterdayString = formatDateOnly(yesterdayDate);

    const yesterdaySuggestion: PredefinedSuggestion = {
      abbreviation: yesterdayString,
      label: 'Yesterday (Absolute)',
    };
    return [...PREDEFINED_SUGGESTIONS, yesterdaySuggestion];
  }, []);

  const parseAndUpdateDate = (newInputValue: string) => {
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
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newInputValue = event.target.value;
    setInputValue(newInputValue);
    parseAndUpdateDate(newInputValue);
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
    parseAndUpdateDate(suggestionValue);

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

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        marginBottom: '5px',
      }}>
      <DateInput
        inputValue={inputValue}
        isInputFocused={isInputFocused}
        isInputHovered={isInputHovered}
        inputRef={inputRef}
        handleInputChange={handleInputChange}
        handleFocus={handleFocus}
        handleBlur={handleBlur}
        handleInputMouseEnter={handleInputMouseEnter}
        handleInputMouseLeave={handleInputMouseLeave}
      />

      <DateTypeLabel inputValue={inputValue} parsedDate={parsedDate} />

      <SuggestionsList
        isDropdownVisible={isDropdownVisible}
        dropdownRef={dropdownRef}
        parsedDate={parsedDate}
        inputValue={inputValue}
        predefinedSuggestions={predefinedSuggestions}
        selectedSuggestion={selectedSuggestion}
        hoveredIndex={hoveredIndex}
        handleSuggestionClick={handleSuggestionClick}
        handleMouseEnter={handleMouseEnter}
        handleMouseLeave={handleMouseLeave}
      />
    </div>
  );
};

// Subcomponents
type DateInputProps = {
  inputValue: string;
  isInputFocused: boolean;
  isInputHovered: boolean;
  inputRef: React.RefObject<HTMLInputElement>;
  handleInputChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleFocus: () => void;
  handleBlur: (event: React.FocusEvent<HTMLInputElement>) => void;
  handleInputMouseEnter: () => void;
  handleInputMouseLeave: () => void;
};

const DateInput: React.FC<DateInputProps> = ({
  inputValue,
  isInputFocused,
  isInputHovered,
  inputRef,
  handleInputChange,
  handleFocus,
  handleBlur,
  handleInputMouseEnter,
  handleInputMouseLeave,
}) => {
  return (
    <>
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
          padding: '4px 12px',
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
    </>
  );
};

type DateTypeLabelProps = {
  inputValue: string;
  parsedDate: Date | null;
};

const DateTypeLabel: React.FC<DateTypeLabelProps> = ({
  inputValue,
  parsedDate,
}) => {
  if (!inputValue.trim()) {
    return null;
  }

  const dateLabel = parsedDate
    ? isRelativeDate(inputValue)
      ? 'Relative'
      : 'Absolute'
    : 'Unparsable';

  return (
    <span
      title={parsedDate ? `Parsed Date: ${formatDate(parsedDate)}` : ''}
      style={{
        position: 'absolute',
        right: '10px',
        top: '50%',
        transform: 'translateY(-50%)',
        fontSize: '12px',
        color: '#333',
        cursor: parsedDate ? 'default' : 'help',
        zIndex: 2, // Ensure the label sits on top of the input
        pointerEvents: 'auto', // Make sure the label can receive pointer events
        backgroundColor: MOON_150,
        padding: '0px 4px',
        borderRadius: '4px',
      }}>
      {dateLabel}
    </span>
  );
};

type ParsedDateInfoProps = {
  parsedDate: Date | null;
  inputValue: string;
};

const ParsedDateInfo: React.FC<ParsedDateInfoProps> = ({
  parsedDate,
  inputValue,
}) => {
  if (!parsedDate) {
    return null;
  }

  return (
    <li
      style={{
        padding: '8px',
        borderBottom: '1px solid #eee',
        color: '#555',
        cursor: 'default',
      }}>
      <strong>{isRelativeDate(inputValue) ? 'Relative:' : 'Absolute:'}</strong>{' '}
      {formatDate(parsedDate)}
    </li>
  );
};

type SuggestionItemProps = {
  suggestion: PredefinedSuggestion;
  index: number;
  isSelected: boolean;
  isHovered: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
  onMouseLeave: () => void;
};

const SuggestionItem: React.FC<SuggestionItemProps> = ({
  suggestion,
  index,
  isSelected,
  isHovered,
  onClick,
  onMouseEnter,
  onMouseLeave,
}) => {
  return (
    <li
      key={index}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        padding: '8px',
        cursor: 'pointer',
        backgroundColor: isSelected
          ? isHovered
            ? '#f8f8f8'
            : '#E1F7FA'
          : isHovered
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
  );
};

type SuggestionsListProps = {
  isDropdownVisible: boolean;
  dropdownRef: React.RefObject<HTMLUListElement>;
  parsedDate: Date | null;
  inputValue: string;
  predefinedSuggestions: PredefinedSuggestion[];
  selectedSuggestion: string | null;
  hoveredIndex: number | null;
  handleSuggestionClick: (suggestionValue: string) => void;
  handleMouseEnter: (index: number) => void;
  handleMouseLeave: () => void;
};

const SuggestionsList: React.FC<SuggestionsListProps> = ({
  isDropdownVisible,
  dropdownRef,
  parsedDate,
  inputValue,
  predefinedSuggestions,
  selectedSuggestion,
  hoveredIndex,
  handleSuggestionClick,
  handleMouseEnter,
  handleMouseLeave,
}) => {
  if (!isDropdownVisible) {
    return null;
  }

  return (
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
      <ParsedDateInfo parsedDate={parsedDate} inputValue={inputValue} />

      {predefinedSuggestions.map((suggestion, index) => (
        <SuggestionItem
          key={index}
          suggestion={suggestion}
          index={index}
          isSelected={selectedSuggestion === suggestion.abbreviation}
          isHovered={hoveredIndex === index}
          onClick={() => handleSuggestionClick(suggestion.abbreviation)}
          onMouseEnter={() => handleMouseEnter(index)}
          onMouseLeave={handleMouseLeave}
        />
      ))}
    </ul>
  );
};
