import React from 'react';

export const FieldLabel: React.FC<{children: React.ReactNode}> = ({
  children,
}) => (
  <div style={{fontWeight: 500, fontSize: 14, marginBottom: 4, marginLeft: 2}}>
    {children}
  </div>
);
