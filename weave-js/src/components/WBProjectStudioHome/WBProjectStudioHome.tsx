import React from 'react';
import * as LE from '../PagePanelComponents/Home/LayoutElements';

export const WBProjectStudioHome: React.FC<{
  entityName: string;
  projectName: string;
}> = () => {
  return (
    <LE.VStack>
      <LE.HBlock
        style={{
          height: '50px',
          borderBottom: '1px solid #ccc',
        }}>
        Title
      </LE.HBlock>

      <LE.HStack>
        <LE.VBlock
          style={{
            width: '300px',
            borderRight: '1px solid #ccc',
          }}>
          side
        </LE.VBlock>
        <LE.VStack>Main</LE.VStack>
      </LE.HStack>
    </LE.VStack>
  );
};
