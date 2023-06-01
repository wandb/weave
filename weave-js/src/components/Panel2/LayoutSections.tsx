import React from 'react';

export const LayoutSections: React.FC<{
  sectionNames: string[];
  renderPanel: (panel: {id: string}) => React.ReactNode;
}> = props => {
  const {sectionNames} = props;
  return (
    <>
      {sectionNames.map((name: string, i: number) => (
        <div>
          <div style={{padding: 4, backgroundColor: '#e8e8e8'}}>{name}</div>
          <div style={{width: '100%', height: 400}}>
            {props.renderPanel({id: name})}
          </div>
        </div>
      ))}
    </>
  );
};
