import styled from 'styled-components';

export const Container = styled.div`
  border-top: 1px solid #e2e8f0;
  padding: 8px 16px;
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
  width: 80px;
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
`;

export const CountIndicator = styled.div`
  width: 60px;
  font-size: 12px;
  color: #64748b;
  flex-shrink: 0;
  text-align: right;
  font-variant-numeric: tabular-nums;
`;

export const ScrubberContent = styled.div`
  flex: 1;
  display: flex;
  gap: 12px;
  align-items: center;
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
    #3b82f6 0%,
    #3b82f6 ${props => props.$progress}%,
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
    background: #3b82f6;
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
    background: #3b82f6;
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

export const BreadcrumbContainer = styled.div`
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  white-space: nowrap;
  font-size: 12px;
  color: #64748b;
  min-height: 32px;
  border-radius: 6px;
  scrollbar-width: none;  /* Firefox */
  -ms-overflow-style: none;  /* IE and Edge */
  
  &::-webkit-scrollbar {
    display: none;  /* Chrome, Safari and Opera */
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
    color: #0F172A;
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
      background: #3B82F6;
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
