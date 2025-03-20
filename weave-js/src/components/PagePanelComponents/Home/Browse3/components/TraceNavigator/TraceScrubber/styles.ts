import * as Colors from '@wandb/weave/common/css/color.styles';
import styled from 'styled-components';

export const Container = styled.div<{$isCollapsed?: boolean}>`
  border-top: 1px solid ${Colors.MOON_200};
  margin-bottom: ${props => (props.$isCollapsed ? '-108px' : '0px')};
  padding: 8px 16px;
  transition: padding 0.2s ease;
  background: ${Colors.WHITE};
`;
Container.displayName = 'Container';

export const CollapseButton = styled.button`
  position: absolute;
  background: ${Colors.MOON_100} !important;
  right: 6px;
  top: -12px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: ${Colors.WHITE};
  border: 1px solid ${Colors.MOON_300};
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  z-index: 1;
  box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);

  &:hover {
    transform: scale(1.05);
    background: ${Colors.MOON_200};
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  }

  &:active {
    transform: scale(0.95);
  }
`;
CollapseButton.displayName = 'CollapseButton';

export const CollapseWrapper = styled.div`
  position: relative;
`;
CollapseWrapper.displayName = 'CollapseWrapper';

export const ScrubberRow = styled.div`
  display: flex;
  align-items: center;
  height: 32px;
  gap: 12px;

  & + & {
    margin-top: 4px;
  }
`;
ScrubberRow.displayName = 'ScrubberRow';

export const Label = styled.div`
  width: 50px;
  font-size: 12px;
  color: ${Colors.MOON_500};
  flex-shrink: 0;
`;
Label.displayName = 'Label';

export const CountIndicator = styled.div`
  width: 50px;
  font-size: 12px;
  color: ${Colors.MOON_500};
  flex-shrink: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
`;
CountIndicator.displayName = 'CountIndicator';

export const ScrubberContent = styled.div`
  flex: 1;
  display: flex;
  gap: 8px;
  align-items: center;
`;
ScrubberContent.displayName = 'ScrubberContent';

export const ArrowButton = styled.button<{disabled?: boolean}>`
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: ${props => (props.disabled ? Colors.MOON_300 : Colors.MOON_500)};
  cursor: ${props => (props.disabled ? 'not-allowed' : 'pointer')};
  transition: all 0.15s ease;
  flex-shrink: 0;

  &:hover:not(:disabled) {
    background: ${Colors.MOON_100};
    color: ${Colors.MOON_900};
  }

  &:active:not(:disabled) {
    transform: scale(0.95);
  }

  svg {
    width: 16px;
    height: 16px;
  }
`;
ArrowButton.displayName = 'ArrowButton';

export const RangeContainer = styled.div`
  flex: 1;
  display: flex;
  gap: 8px;
  align-items: center;

  /* Ensure the numeric indicator is always at the end */
  & > ${CountIndicator} {
    margin-left: auto;
  }
`;
RangeContainer.displayName = 'RangeContainer';

export const SliderContainer = styled.div`
  flex: 1;
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0; /* Ensure flex shrinking works properly */
`;
SliderContainer.displayName = 'SliderContainer';

interface RangeInputProps {
  $progress: number;
}

export const RangeInput = styled.input<RangeInputProps>`
  -webkit-appearance: none;
  width: 100%;
  height: 8px;
  background: linear-gradient(
    to right,
    ${Colors.TEAL_500} 0%,
    ${Colors.TEAL_500} ${props => props.$progress}%,
    ${Colors.MOON_200} ${props => props.$progress}%,
    ${Colors.MOON_200} 100%
  );
  border-radius: 4px;
  cursor: pointer;

  &::-webkit-slider-runnable-track {
    width: 100%;
    height: 8px;
    background: transparent;
    border-radius: 4px;
  }

  &::-webkit-slider-thumb {
    -webkit-appearance: none;
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: ${Colors.TEAL_500};
    border: 2px solid ${Colors.WHITE};
    margin-top: -4px;
    transition: transform 0.1s;
  }

  &::-webkit-slider-thumb:hover {
    transform: scale(1.1);
  }

  &::-moz-range-track {
    width: 100%;
    height: 8px;
    background: transparent;
    border-radius: 4px;
  }

  &::-moz-range-thumb {
    height: 16px;
    width: 16px;
    border-radius: 50%;
    background: ${Colors.TEAL_500};
    border: 2px solid ${Colors.WHITE};
    transition: transform 0.1s;
  }

  &::-moz-range-thumb:hover {
    transform: scale(1.1);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;
RangeInput.displayName = 'RangeInput';

export const TooltipContainer = styled.div`
  position: relative;
  display: inline-flex;
  align-items: center;
`;
TooltipContainer.displayName = 'TooltipContainer';

export const TooltipContent = styled.div`
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: ${Colors.MOON_800};
  color: ${Colors.WHITE};
  border-radius: 6px;
  font-size: 12px;
  white-space: nowrap;
  z-index: 10;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.2s, visibility 0.2s;

  ${TooltipContainer}:hover & {
    opacity: 1;
    visibility: visible;
  }

  &::after {
    content: '';
    position: absolute;
    top: 100%;
    left: 16px;
    border: 6px solid transparent;
    border-top-color: ${Colors.MOON_800};
  }
`;
TooltipContent.displayName = 'TooltipContent';

export const BreadcrumbWrapper = styled.div`
  display: flex;
  align-items: center;
  overflow-x: hidden;
  font-size: 12px;
  color: ${Colors.MOON_500};
  min-height: 32px;
  border-bottom: 1px solid ${Colors.MOON_200};
  background: ${Colors.MOON_100};
`;
BreadcrumbWrapper.displayName = 'BreadcrumbWrapper';

export const BreadcrumbNavigationButtons = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-right: 1px solid ${Colors.MOON_200};
`;
BreadcrumbNavigationButtons.displayName = 'BreadcrumbNavigationButtons';

export const BreadcrumbList = styled.div`
  padding: 4px 16px;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  white-space: nowrap;
  scrollbar-width: none; /* Firefox */
  -ms-overflow-style: none; /* IE and Edge */

  &::-webkit-scrollbar {
    display: none; /* Chrome, Safari and Opera */
  }
`;
BreadcrumbList.displayName = 'BreadcrumbList';

export const BreadcrumbItem = styled.button<{$active?: boolean}>`
  padding: 0px 4px !important;
  border-radius: 4px !important;
  background: ${props => (props.$active ? Colors.MOON_200 : 'transparent')};
  color: ${props => (props.$active ? Colors.MOON_900 : Colors.MOON_500)};
  font-weight: ${props => (props.$active ? '500' : '400')};
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  line-height: 1.2;
  position: relative;

  &:hover {
    background: ${props => (props.$active ? Colors.MOON_200 : Colors.MOON_100)};
    color: ${Colors.MOON_900};
  }

  &:active {
    transform: scale(0.98);
  }

  ${props =>
    props.$active &&
    `
    &::after {
      content: '';
      position: absolute;
      bottom: -1px;
      left: 4px;
      right: 4px;
      height: 2px;
      background: ${Colors.TEAL_500};
      border-radius: 1px;
    }
  `}
`;
BreadcrumbItem.displayName = 'BreadcrumbItem';

export const BreadcrumbSeparator = styled.span`
  color: ${Colors.MOON_400};
  user-select: none;
  font-size: 14px;
  margin: 0 -2px;
  opacity: 0.6;
`;
BreadcrumbSeparator.displayName = 'BreadcrumbSeparator';
