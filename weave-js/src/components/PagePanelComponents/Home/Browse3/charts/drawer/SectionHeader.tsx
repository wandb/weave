import React from 'react';

export const SectionHeader: React.FC<{
  children: React.ReactNode;
  first?: boolean;
}> = ({children, first = false}) => (
  <div
    style={{
      textTransform: 'uppercase',
      fontSize: 12,
      color: '#888',
      fontWeight: 600,
      margin: `${first ? '0' : '12px'} 0 4px 0`,
      letterSpacing: 1,
    }}>
    {children}
  </div>
);
