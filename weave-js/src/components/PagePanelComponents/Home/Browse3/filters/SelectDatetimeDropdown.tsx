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
import {formatDate, formatDateOnly, parseDate} from '../../../../../util/date';
import {FILTER_INPUT_DEBOUNCE_MS} from './FilterBar';

type PredefinedSuggestion = {
  abbreviation: string;
  label: string;
  absoluteDateTime?: string;
  isCustomDate?: boolean;
};

const PREDEFINED_SUGGESTIONS: PredefinedSuggestion[] = [
  {abbreviation: '1h', label: '1 Hour'},
  {abbreviation: '1d', label: '1 Day'},
  {abbreviation: '2d', label: '2 Days'},
  {abbreviation: '1w', label: '1 Week'},
  {abbreviation: '1mo', label: '1 Month'},
  {abbreviation: 'custom', label: 'Custom datetime', isCustomDate: true},
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
  const [inputValue, setInputValue] = useState('');
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
  const suggestionClickedRef = useRef<boolean>(false);

  // Format and set input value whenever the value prop changes
  useEffect(() => {
    if (value) {
      const date = parseDate(value);
      if (date) {
        const formattedDate = formatDate(date);
        setInputValue(formattedDate);
        setIsInvalid(false);
      } else {
        // If parseDate fails, use the raw value as fallback
        setInputValue(value);
      }
    } else {
      setInputValue('');
    }
  }, [value]);

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
      // Skip adding absoluteDateTime for the custom date option
      if (suggestion.isCustomDate) {
        return suggestion;
      }

      const date = parseDate(suggestion.abbreviation)!;

      // Format the date differently if time is 00:00:00
      const onlyDate =
        date.getHours() === 0 &&
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
        if (skipDebounce && debounceTimeoutRef.current) {
          clearTimeout(debounceTimeoutRef.current);
        }
        const formattedDate = formatDate(date);
        setInputValue(formattedDate);
        onChange(formattedDate);
        setIsInvalid(false);
      } else {
        // Don't update the filter state when input is invalid
        // Just mark it as invalid and keep the current input value
        setIsInvalid(true);
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
      }, FILTER_INPUT_DEBOUNCE_MS);
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

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      // Immediately parse the current input value
      parseAndUpdateDate(inputValue, true);
      setDropdownVisible(false);
      if (inputRef.current) {
        inputRef.current.blur();
      }
    }
  };

  const handleDateChange = (date: Date | null) => {
    if (date) {
      const formattedDate = formatDate(date);
      setInputValue(formattedDate);
      setIsInvalid(false);
      // Don't auto update the date until the calendar is closed
    }
  };

  const handleIconClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    setIsCalendarOpen(prev => !prev);
  };

  // Add handler for closing when Ok button is clicked
  const handleClose = (date: Date | null) => {
    setIsCalendarOpen(false);
    setDropdownVisible(false);
    if (inputRef.current) {
      inputRef.current.blur();
    }

    if (date) {
      // When OK is clicked, use the provided date
      const formattedDate = formatDate(date);
      parseAndUpdateDate(formattedDate, true);
    } else {
      // When clicking outside, parse immediately if the input value has changed
      if (inputValue !== value) {
        parseAndUpdateDate(inputValue, true);
      }
    }
  };

  const handleSuggestionClick = useCallback(
    (
      suggestionValue: string,
      absoluteDateTime?: string,
      isCustomDate?: boolean
    ) => {
      if (isCustomDate) {
        setIsCalendarOpen(true);
        return;
      }
      // Use the absolute date time if provided, otherwise use the abbreviation
      const valueToUse = absoluteDateTime || suggestionValue;
      setInputValue(valueToUse);

      // Skip debounce when selecting from suggestions
      parseAndUpdateDate(suggestionValue, true);

      setSelectedSuggestion(suggestionValue);
      setDropdownVisible(false);
      setIsInvalid(false);

      // Set flag to prevent blur handler from reverting the value
      suggestionClickedRef.current = true;

      if (inputRef.current) {
        inputRef.current.blur();
      }

      // Reset flag after a short delay
      setTimeout(() => {
        suggestionClickedRef.current = false;
      }, 100);
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
            onKeyDown={handleKeyDown}
            onFocus={() => setDropdownVisible(true)}
            onBlur={event => {
              if (
                dropdownRef.current &&
                !dropdownRef.current.contains(event.relatedTarget as Node)
              ) {
                setDropdownVisible(false);
              }
              setIsInputFocused(false);

              // When user leaves the input, immediately parse what they've typed
              // Skip parsing if a suggestion was just clicked to prevent race condition
              if (inputValue !== value && !suggestionClickedRef.current) {
                parseAndUpdateDate(inputValue, true);
              }
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
            onClose={() => handleClose(null)}
            value={new Date(inputValue) ?? null}
            onChange={handleDateChange}
            onAccept={handleClose}
            reduceAnimations
            closeOnSelect={false}
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
                  '& .MuiPickersDay-root.Mui-selected': {
                    backgroundColor: TEAL_500,
                    '&:hover': {
                      backgroundColor: TEAL_400,
                    },
                    '&:focus': {
                      backgroundColor: TEAL_500,
                    },
                  },
                  '& .MuiButton-root': {
                    fontFamily: 'Source Sans Pro',
                    color: TEAL_500,
                    '&:hover': {
                      backgroundColor: 'rgba(0, 140, 140, 0.1)',
                    },
                  },
                  '& .MuiPickersCalendarHeader-switchViewButton': {
                    color: TEAL_500,
                  },
                  '& .MuiPickersYear-yearButton.MuiPickersYear-yearButton.MuiPickersYear-yearButton':
                    {
                      fontFamily: 'Source Sans Pro',
                      '&.Mui-selected': {
                        backgroundColor: TEAL_500,
                        color: WHITE,
                      },
                    },
                  '& .MuiButtonBase-root.MuiMultiSectionDigitalClockSection-item.MuiMultiSectionDigitalClockSection-item.Mui-selected':
                    {
                      backgroundColor: TEAL_500,
                      color: WHITE,
                    },
                },
              },
              actionBar: {
                sx: {
                  '& .MuiButton-root': {
                    fontFamily: 'Source Sans Pro',
                    color: TEAL_500,
                    '&:hover': {
                      backgroundColor: 'rgba(0, 140, 140, 0.1)',
                    },
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
  const isCustomDate = suggestion.isCustomDate;

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
        borderTop: isCustomDate ? `1px solid ${MOON_200}` : 'none',
      }}
      onMouseDown={e => e.preventDefault()}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
        {isCustomDate ? (
          <span style={{display: 'flex', alignItems: 'center'}}>
            <Icon name="date" style={{marginRight: '4px', fontSize: '14px'}} />
            {suggestion.label}
          </span>
        ) : (
          <span>{suggestion.absoluteDateTime}</span>
        )}
        {!isCustomDate && (
          <span style={{color: MOON_500}}>{suggestion.abbreviation}</span>
        )}
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
  handleSuggestionClick: (
    suggestionValue: string,
    absoluteDateTime?: string,
    isCustomDate?: boolean
  ) => void;
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
          onClick={() =>
            handleSuggestionClick(
              suggestion.abbreviation,
              suggestion.absoluteDateTime,
              suggestion.isCustomDate
            )
          }
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
    // We only care about users opening the drawer and changing
    // the value, ignore if not changed.
    if (inputValue === date) {
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
