import styled from 'styled-components';

export const Container = styled.div`
  border-top: 1px solid #E2E8F0;
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
  color: #64748B;
  flex-shrink: 0;
`;

export const CountIndicator = styled.div`
  width: 60px;
  font-size: 12px;
  color: #64748B;
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
    #3B82F6 0%,
    #3B82F6 ${props => props.$progress}%,
    #E2E8F0 ${props => props.$progress}%,
    #E2E8F0 100%
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
    background: #3B82F6;
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
    background: #3B82F6;
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
  background: #1E293B;
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
    border-top-color: #1E293B;
  }
`;

export const BreadcrumbContainer = styled.div`
  margin-top: 8px;
  padding: 4px 0;
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  white-space: nowrap;
  font-size: 11px;
  color: #64748B;

  &::-webkit-scrollbar {
    height: 2px;
  }

  &::-webkit-scrollbar-track {
    background: #F1F5F9;
  }

  &::-webkit-scrollbar-thumb {
    background: #CBD5E1;
    border-radius: 1px;
  }
`;

export const BreadcrumbItem = styled.button<{$active?: boolean}>`
  padding: 2px 6px;
  border-radius: 4px;
  background: ${props => props.$active ? '#E2E8F0' : 'transparent'};
  color: ${props => props.$active ? '#1E293B' : '#64748B'};
  font-weight: ${props => props.$active ? '500' : '400'};
  cursor: pointer;
  border: none;
  transition: all 0.1s;

  &:hover {
    background: #F1F5F9;
    color: #1E293B;
  }
`;

export const BreadcrumbSeparator = styled.span`
  color: #94A3B8;
  user-select: none;
`; 