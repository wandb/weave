import {AdapterDateFns} from '@mui/x-date-pickers/AdapterDateFns';
import {DateTimePicker} from '@mui/x-date-pickers/DateTimePicker';
import {LocalizationProvider} from '@mui/x-date-pickers/LocalizationProvider';
import {
  MOON_100,
  MOON_200,
  MOON_250,
  MOON_500,
  RED_300,
  TEAL_350,
  TEAL_400,
  TEAL_500,
  WHITE,
} from '@wandb/weave/common/css/color.styles';
import {Icon} from '@wandb/weave/components/Icon';
import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';

import * as userEvents from '../../../../../integrations/analytics/userEvents';
import {
  formatDate,
  formatDateOnly,
  parseDate,
  utcToLocalTimeString,
} from '../../../../../util/date';

type PredefinedSuggestion = {
  abbreviation: string;
  label: string;
  absoluteDateTime?: string;
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
  entity: string;
  project: string;
  value: string;
  onChange: (value: string) => void;
  isActive?: boolean;
};

export const SelectDatetimeDropdown: React.FC<SelectDatetimeDropdownProps> = ({
  entity,
  project,
  value,
  onChange,
  isActive,
}) => {
  // We have to play this game because
  const [inputValue, setInputValue] = useState(utcToLocalTimeString(value));
  const [isDropdownVisible, setDropdownVisible] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState<string | null>(
    null
  );
  const [isInputHovered, setIsInputHovered] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);
  const [isCalendarOpen, setIsCalendarOpen] = useState(false);
  const [isIconHovered, setIsIconHovered] = useState(false);
  const [isInvalid, setIsInvalid] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);
  const debounceTimeoutRef = useRef<NodeJS.Timeout>();

  // Set default value to 1mo if no valid date
  useEffect(() => {
    if (!value) {
      const defaultDate = parseDate('1mo');
      if (defaultDate) {
        const utcDate = formatDate(defaultDate, 'YYYY-MM-DD HH:mm:ss', true);
        onChange(utcDate);
        setInputValue(utcToLocalTimeString(utcDate));
      }
    }
    // Only run on first render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Add analytics hook
  useFireAnalyticsForDateFilterDropdownUsed(entity, project, inputValue, value);

  // Auto-expand dropdown when active
  useEffect(() => {
    if (isActive && inputRef.current) {
      inputRef.current.focus();
      setDropdownVisible(true);
      setIsInputFocused(true);
    }
  }, [isActive]);

  const predefinedSuggestions = useMemo(() => {
    // Map all predefined suggestions to include absolute datetime
    return PREDEFINED_SUGGESTIONS.map(suggestion => {
      const date = parseDate(suggestion.abbreviation)!;
      
      // Format the date differently if time is 00:00:00
      const onlyDate = date.getHours() === 0 && 
                      date.getMinutes() === 0 && 
                      date.getSeconds() === 0;
      
      const formattedDateTime = onlyDate 
        ? formatDateOnly(date) 
        : formatDate(date);
      
      return {
        ...suggestion,
        absoluteDateTime: formattedDateTime,
      };
    });
  }, []);

  const parseAndUpdateDate = useCallback(
    (newInputValue: string, skipDebounce = false) => {
      const date = parseDate(newInputValue);
      if (date) {
        const utcDate = formatDate(date, 'YYYY-MM-DD HH:mm:ss', true);
        onChange(utcDate);
        setIsInvalid(false);
      } else {
        setIsInvalid(true);
        onChange('');
      }
    },
    [onChange]
  );

  const debouncedInputChange = useCallback(
    (newInputValue: string) => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
      debounceTimeoutRef.current = setTimeout(() => {
        parseAndUpdateDate(newInputValue);
      }, 500);
    },
    [parseAndUpdateDate]
  );

  // Cleanup debounce timeout on unmount
  useEffect(() => {
    return () => {
      if (debounceTimeoutRef.current) {
        clearTimeout(debounceTimeoutRef.current);
      }
    };
  }, []);

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newInputValue = event.target.value;
    setInputValue(newInputValue);
    debouncedInputChange(newInputValue);

    // Check against our predefined suggestions by their value
    const isPredefined = predefinedSuggestions.some(
      s => s.abbreviation === newInputValue
    );
    if (!isPredefined) {
      setSelectedSuggestion(null);
    }
  };

  const handleDateChange = (date: Date | null) => {
    if (date) {
      setInputValue(formatDate(date));
      const utcDate = formatDate(date, 'YYYY-MM-DD HH:mm:ss', true);
      onChange(utcDate);
      setIsInvalid(false);
    }
  };

  const handleIconClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    setIsCalendarOpen(true);
  };

  // Add handler for closing when Ok button is clicked
  const handleAccept = (date: Date | null) => {
    if (date) {
      setIsCalendarOpen(false);
    }
  };

  const handleSuggestionClick = useCallback(
    (suggestionValue: string, absoluteDateTime?: string) => {
      // Use the absolute date time if provided, otherwise use the abbreviation
      const valueToUse = absoluteDateTime || suggestionValue;
      setInputValue(valueToUse);
      
      // Skip debounce when selecting from suggestions
      parseAndUpdateDate(suggestionValue, true);

      setSelectedSuggestion(suggestionValue);
      setDropdownVisible(false);
      if (inputRef.current) {
        inputRef.current.blur();
      }
    },
    [parseAndUpdateDate]
  );

  const handleMouseEnter = useCallback(
    (index: number) => {
      setHoveredIndex(index);
    },
    [setHoveredIndex]
  );

  const handleMouseLeave = useCallback(() => {
    setHoveredIndex(null);
  }, [setHoveredIndex]);

  // Memoize the suggestions list component to prevent unnecessary re-renders
  const suggestionsList = useMemo(
    () => (
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
    ),
    [
      isDropdownVisible,
      predefinedSuggestions,
      selectedSuggestion,
      hoveredIndex,
      handleSuggestionClick,
      handleMouseEnter,
      handleMouseLeave,
    ]
  );

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
      }}>
      <LocalizationProvider dateAdapter={AdapterDateFns}>
        <div style={{position: 'relative', width: '100%'}}>
          <Icon
            name="date"
            style={{
              position: 'absolute',
              top: '50%',
              right: '9px',
              transform: 'translateY(-50%)',
              fontSize: '16px',
              cursor: 'pointer',
              color: isIconHovered ? TEAL_500 : 'inherit',
            }}
            onClick={handleIconClick}
            onMouseEnter={() => setIsIconHovered(true)}
            onMouseLeave={() => setIsIconHovered(false)}
          />
          <input
            type="text"
            aria-label="Date input"
            value={inputValue}
            onChange={handleInputChange}
            onFocus={() => setDropdownVisible(true)}
            onBlur={event => {
              if (
                dropdownRef.current &&
                !dropdownRef.current.contains(event.relatedTarget as Node)
              ) {
                setDropdownVisible(false);
              }
              setIsInputFocused(false);
            }}
            onMouseEnter={() => setIsInputHovered(true)}
            onMouseLeave={() => setIsInputHovered(false)}
            placeholder="Enter a date..."
            style={{
              padding: '4px 12px',
              paddingLeft: '8px',
              paddingRight: '34px',
              borderRadius: '4px',
              border: 0,
              boxShadow: isInputFocused
                ? `0 0 0 2px ${isInvalid ? RED_300 : TEAL_400}`
                : isInputHovered || isIconHovered
                ? `0 0 0 2px ${isInvalid ? RED_300 : TEAL_350}`
                : `inset 0 0 0 1px ${isInvalid ? RED_300 : MOON_250}`,
              outline: 'none',
              flex: 1,
              height: '32px',
              minHeight: '32px',
              boxSizing: 'border-box',
              fontSize: '16px',
              lineHeight: '24px',
              cursor: 'default',
              width: '100%',
              color: isInvalid ? '#ff4d4f' : 'inherit',
            }}
            ref={inputRef}
          />
          <DateTimePicker
            open={isCalendarOpen}
            onClose={() => setIsCalendarOpen(false)}
            value={parseDate(inputValue) ?? null}
            onChange={handleDateChange}
            onAccept={handleAccept}
            slotProps={{
              textField: {
                style: {display: 'none'},
              },
              popper: {
                style: {
                  zIndex: 9999,
                  marginTop: '4px',
                  fontFamily: 'Source Sans Pro',
                },
                anchorEl: inputRef.current,
                placement: 'bottom-start',
                modifiers: [
                  {
                    name: 'offset',
                    options: {
                      offset: [0, 2],
                    },
                  },
                  {
                    name: 'flip',
                    enabled: true,
                  },
                  {
                    name: 'preventOverflow',
                    enabled: true,
                    options: {
                      boundariesElement: 'viewport',
                    },
                  },
                ],
              },
              desktopPaper: {
                style: {
                  boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)',
                  borderRadius: '4px',
                  border: `1px solid ${MOON_200}`,
                  fontFamily: 'Source Sans Pro',
                },
              },
              layout: {
                sx: {
                  fontFamily: 'Source Sans Pro',
                  '& *': {
                    fontFamily: 'Source Sans Pro',
                  },
                },
              },
            }}
            ampm={false}
            format="yyyy-MM-dd HH:mm:ss"
          />
        </div>
      </LocalizationProvider>

      {suggestionsList}
    </div>
  );
};

// Subcomponents
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
        <span>{suggestion.absoluteDateTime}</span>
        <span style={{color: MOON_500}}>
          {suggestion.abbreviation}
        </span>
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
  handleSuggestionClick: (suggestionValue: string, absoluteDateTime?: string) => void;
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
          onClick={() => handleSuggestionClick(suggestion.abbreviation, suggestion.absoluteDateTime)}
          onMouseEnter={() => handleMouseEnter(index)}
          onMouseLeave={handleMouseLeave}
        />
      ))}
    </ul>
  );
};

/**
 * Fires an analytics event when the metrics plots are viewed.
 * This is used to track the usage and latency of the metrics plots.
 * Only fires once when opened.
 */
const useFireAnalyticsForDateFilterDropdownUsed = (
  entity: string,
  project: string,
  inputValue: string,
  date: string
) => {
  const sentEvent = useRef(false);
  useEffect(() => {
    if (sentEvent.current) {
      return;
    }
    userEvents.dateFilterDropdownUsed({
      entity,
      project,
      rawInput: inputValue,
      date,
    });
    sentEvent.current = true;
  }, [entity, project, inputValue, date]);
};
