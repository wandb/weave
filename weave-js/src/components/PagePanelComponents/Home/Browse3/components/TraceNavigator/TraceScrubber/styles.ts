import styled from 'styled-components';

export const Container = styled.div<{$isCollapsed?: boolean}>`
  border-top: 1px solid #e2e8f0;
  margin-bottom: ${props => (props.$isCollapsed ? '-110px' : '0px')};
  padding: 8px 16px;
  transition: padding 0.2s ease;
  background: #fff;
`;

export const CollapseButton = styled.button`
  position: absolute;
  background: #f8fafc !important;
  right: 6px;
  top: -12px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #fff;
  border: 1px solid #d4d5d9;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  z-index: 1;
  box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);

  &:hover {
    transform: scale(1.05);
    background: #e8e8e9;
    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
  }

  &:active {
    transform: scale(0.95);
  }
`;

export const CollapseWrapper = styled.div`
  position: relative;
`;

export const ScrubberRow = styled.div`
  display: flex;
  align-items: center;
  height: 32px;
  gap: 12px;

  & + & {
    margin-top: 4px;
  }
`;

export const Label = styled.div`
  width: 50px;
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
`;

export const CountIndicator = styled.div`
  width: 50px;
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
`;

export const ScrubberContent = styled.div`
  flex: 1;
  display: flex;
  gap: 8px;
  align-items: center;
`;

export const ArrowButton = styled.button<{disabled?: boolean}>`
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: ${props => (props.disabled ? '#CBD5E1' : '#64748B')};
  cursor: ${props => (props.disabled ? 'not-allowed' : 'pointer')};
  transition: all 0.15s ease;
  flex-shrink: 0;

  &:hover:not(:disabled) {
    background: #f1f5f9;
    color: #0f172a;
  }

  &:active:not(:disabled) {
    transform: scale(0.95);
  }

  svg {
    width: 16px;
    height: 16px;
  }
`;

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

export const SliderContainer = styled.div`
  flex: 1;
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0; /* Ensure flex shrinking works properly */
`;

interface RangeInputProps {
  $progress: number;
}

export const RangeInput = styled.input<RangeInputProps>`
  -webkit-appearance: none;
  width: 100%;
  height: 8px;
  background: linear-gradient(
    to right,
    #13a9ba 0%,
    #13a9ba ${props => props.$progress}%,
    #e2e8f0 ${props => props.$progress}%,
    #e2e8f0 100%
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
    background: #13a9ba;
    border: 2px solid white;
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
    background: #13a9ba;
    border: 2px solid white;
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

export const TooltipContainer = styled.div`
  position: relative;
  display: inline-flex;
  align-items: center;
`;

export const TooltipContent = styled.div`
  position: absolute;
  bottom: 100%;
  left: 0;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: #1e293b;
  color: white;
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
    border-top-color: #1e293b;
  }
`;

export const BreadcrumbWrapper = styled.div`
  display: flex;
  align-items: center;
  overflow-x: hidden;
  font-size: 12px;
  color: #64748b;
  min-height: 32px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
`;

export const BreadcrumbNavigationButtons = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-right: 1px solid #e2e8f0;
`;

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

export const BreadcrumbItem = styled.button<{$active?: boolean}>`
  padding: 0px 4px !important;
  border-radius: 4px !important;
  background: ${props => (props.$active ? '#E2E8F0' : 'transparent')};
  color: ${props => (props.$active ? '#0F172A' : '#64748B')};
  font-weight: ${props => (props.$active ? '500' : '400')};
  cursor: pointer;
  border: none;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  line-height: 1.2;
  position: relative;

  &:hover {
    background: ${props => (props.$active ? '#E2E8F0' : '#F1F5F9')};
    color: #0f172a;
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
      background: #13A9BA;
      border-radius: 1px;
    }
  `}
`;

export const BreadcrumbSeparator = styled.span`
  color: #94a3b8;
  user-select: none;
  font-size: 14px;
  margin: 0 -2px;
  opacity: 0.6;
`;
