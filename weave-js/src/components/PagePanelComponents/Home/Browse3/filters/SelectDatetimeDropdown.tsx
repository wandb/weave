import {
  MOON_100,
  MOON_200,
  MOON_250,
  MOON_500,
  TEAL_350,
  TEAL_400,
  WHITE,
} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useMemo, useRef, useState} from 'react';

import {formatDate, formatDateOnly, parseDate} from '../../../../../util/date';

type PredefinedSuggestion = {
  abbreviation: string;
  label: string;
};

const PREDEFINED_SUGGESTIONS: PredefinedSuggestion[] = [
  {abbreviation: '1h', label: '1 Hour'},
  {abbreviation: '1d', label: '1 Day'},
  {abbreviation: '2d', label: '2 Days'},
  {abbreviation: '1w', label: '1 Week'},
  {abbreviation: '1mo', label: '1 Month'},
  {abbreviation: '3mo', label: '3 Months'},
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
  const [isDropdownVisible, setDropdownVisible] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(
    null
  );
  const [isInputHovered, setIsInputHovered] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);

  // Compute yesterday's date string (date only, no time)
  const predefinedSuggestions: PredefinedSuggestion[] = useMemo(() => {
    const yesterdayDate = new Date();
    yesterdayDate.setDate(yesterdayDate.getDate() - 1);
    const yesterdayString = formatDateOnly(yesterdayDate);

    const yesterdaySuggestion: PredefinedSuggestion = {
      abbreviation: yesterdayString,
      label: 'Yesterday',
    };
    return [...PREDEFINED_SUGGESTIONS, yesterdaySuggestion];
  }, []);

  const parseAndUpdateDate = (newInputValue: string) => {
    // Parse the input to get a date
    const date = parseDate(newInputValue);

    // Call the parent onChange handler with the timestamp
    if (date) {
      onChange(formatDate(date));
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

      <SuggestionsList
        isDropdownVisible={isDropdownVisible}
        dropdownRef={dropdownRef}
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
        aria-label="Date input"
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
          paddingRight: '8px',
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
      role="option"
      aria-selected={isSelected}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        padding: '8px',
        cursor: 'pointer',
        backgroundColor: isSelected
          ? isHovered
            ? MOON_100
            : '#E1F7FA' // special super light teal
          : isHovered
          ? MOON_100
          : WHITE,
      }}
      onMouseDown={e => e.preventDefault()}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
        <span>{suggestion.abbreviation}</span>
        <span style={{color: MOON_500}}>{suggestion.label}</span>
      </div>
    </li>
  );
};

type SuggestionsListProps = {
  isDropdownVisible: boolean;
  dropdownRef: React.RefObject<HTMLUListElement>;
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
      role="listbox"
      style={{
        position: 'absolute',
        top: '100%',
        left: '0',
        right: '0',
        backgroundColor: WHITE,
        border: `1px solid ${MOON_200}`,
        borderRadius: '4px',
        marginTop: '4px',
        listStyle: 'none',
        fontSize: '14px',
        padding: '0',
        overflow: 'hidden',
        zIndex: 1000,
      }}>
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
