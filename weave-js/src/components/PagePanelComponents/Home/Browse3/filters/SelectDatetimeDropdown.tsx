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
import {AdapterDateFns} from '@mui/x-date-pickers/AdapterDateFns';
import {DateTimePicker} from '@mui/x-date-pickers/DateTimePicker';
import {LocalizationProvider} from '@mui/x-date-pickers/LocalizationProvider';
import React, {useEffect, useMemo, useRef, useState} from 'react';

import * as userEvents from '../../../../../integrations/analytics/userEvents';
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
  entity: string;
  project: string;
  value: string;
  onChange: (value: string) => void;
};

export const SelectDatetimeDropdown: React.FC<SelectDatetimeDropdownProps> = ({
  entity,
  project,
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
  const [isCalendarOpen, setIsCalendarOpen] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);

  // Add analytics hook
  useFireAnalyticsForDateFilterDropdownUsed(entity, project, inputValue, value);

  const predefinedSuggestions: PredefinedSuggestion[] = useMemo(() => {
    const yesterdaySuggestion = parseDate('yesterday')!;
    return [
      ...PREDEFINED_SUGGESTIONS,
      {
        abbreviation: formatDateOnly(yesterdaySuggestion),
        label: 'Yesterday',
      },
    ];
  }, []);

  const parseAndUpdateDate = (newInputValue: string) => {
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

  const handleDateChange = (date: Date | null) => {
    if (date) {
      const formattedDate = formatDate(date);
      setInputValue(formattedDate);
      onChange(formattedDate);
      setIsCalendarOpen(false);
    }
  };

  const handleIconClick = (event: React.MouseEvent) => {
    event.stopPropagation();
    setIsCalendarOpen(true);
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

  return (
    <div
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        marginBottom: '5px',
      }}>
      <LocalizationProvider dateAdapter={AdapterDateFns}>
        <div style={{position: 'relative', width: '100%'}}>
          <Icon
            name="date"
            style={{
              position: 'absolute',
              top: '50%',
              left: '9px',
              transform: 'translateY(-50%)',
              fontSize: '16px',
              cursor: 'pointer',
              zIndex: 1,
            }}
            onClick={handleIconClick}
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
              paddingLeft: '34px',
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
              width: '100%',
            }}
            ref={inputRef}
          />
          <DateTimePicker
            open={isCalendarOpen}
            onClose={() => setIsCalendarOpen(false)}
            value={parseDate(inputValue) || null}
            onChange={handleDateChange}
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
          paddingLeft: '36px',
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
