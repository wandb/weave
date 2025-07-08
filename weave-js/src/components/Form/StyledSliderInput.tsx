import {
  MOON_250,
  MOON_350,
  TEAL_500,
} from '@wandb/weave/common/css/color.styles';
import React, {useRef} from 'react';

interface StyledSliderInputProps {
  progress: number;
  className?: string;
  children: React.ReactNode;
}

export const StyledSliderInput: React.FC<StyledSliderInputProps> = ({
  progress,
  className,
  children,
}) => {
  const uniqueId = useRef(`slider-${Math.random().toString(36).substr(2, 9)}`);

  return (
    <>
      <style>
        {`
          .${uniqueId.current} .slider-input input[type='range'] {
            appearance: none;
            -webkit-appearance: none;
            width: 100%;
            height: 8px;
            border-radius: 4px;
            background: linear-gradient(
              to right,
              ${TEAL_500} 0%,
              ${TEAL_500} ${progress}%,
              ${MOON_250} ${progress}%,
              ${MOON_250} 100%
            );
            outline: none;
            padding: 0;
            margin: 8px 0;
          }

          .${uniqueId.current} .slider-input input[type='range']::-webkit-slider-track {
            width: 100%;
            height: 8px;
            border-radius: 4px;
            background: transparent;
          }

          .${uniqueId.current} .slider-input input[type='range']::-moz-range-track {
            width: 100%;
            height: 8px;
            border-radius: 4px;
            background: transparent;
          }

          .${uniqueId.current} .slider-input input[type='range']::-webkit-slider-thumb {
            appearance: none;
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: #fff;
            cursor: pointer;
            border: 1px solid ${MOON_350};
            box-shadow: 0 0 2px 0px rgba(0, 0, 0, 0.1);
            transition: box-shadow 0.2s;
          }

          .${uniqueId.current} .slider-input input[type='range']::-webkit-slider-thumb:hover {
            box-shadow: 0 0 8px 0px rgba(0, 0, 0, 0.2);
          }

          .${uniqueId.current} .slider-input input[type='range']::-moz-range-thumb {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #fff;
            cursor: pointer;
            border: 1px solid ${MOON_350};
            box-shadow: 0 0 2px 0px rgba(0, 0, 0, 0.1);
            transition: box-shadow 0.2s;
          }

          .${uniqueId.current} .slider-input input[type='range']::-moz-range-thumb:hover {
            box-shadow: 0 0 8px 0px rgba(0, 0, 0, 0.2);
          }
        `}
      </style>
      <div className={`${uniqueId.current} ${className || ''}`}>{children}</div>
    </>
  );
};
