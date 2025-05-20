import React from 'react';

type OrbProps = {
  color?: string;
  pulse?: boolean;
  size?: number;
};

export const Orb = ({color = 'blue', pulse = false, size = 20}: OrbProps) => {
  return (
    <div
      style={{
        height: size,
        width: size,
        borderRadius: '50%',
        background: `radial-gradient(circle at 30% 30%, ${color}-400, ${color}-600)`,
        boxShadow: `
          0 10px 15px -3px rgba(0, 0, 0, 0.1),
          0 4px 6px -2px rgba(0, 0, 0, 0.05),
          0 0 0 1px ${
            color === 'blue'
              ? 'rgba(59, 130, 246, 0.5)'
              : color === 'red'
              ? 'rgba(239, 68, 68, 0.5)'
              : color === 'green'
              ? 'rgba(34, 197, 94, 0.5)'
              : color === 'yellow'
              ? 'rgba(234, 179, 8, 0.5)'
              : 'rgba(107, 114, 128, 0.5)'
          },
          inset 0 -2px 5px rgba(0, 0, 0, 0.2),
          inset 2px 2px 5px rgba(255, 255, 255, 0.3)
        `,
        animation: pulse
          ? 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite'
          : 'none',
      }}
    />
  );
};
