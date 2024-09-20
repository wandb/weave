import React from 'react';

type PlaceholdersPanelProps = {
  placeholders: any[]; // TODO
};

export const PlaceholdersPanel = ({placeholders}: PlaceholdersPanelProps) => {
  return (
    <div>
      {placeholders.map(p => (
        <div>
          {p.type} {p.name}
        </div>
      ))}
    </div>
  );
};
