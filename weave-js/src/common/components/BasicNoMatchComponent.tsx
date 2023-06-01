import React from 'react';
import {Header} from 'semantic-ui-react';

export const BasicNoMatchComponent = () => {
  return (
    <div className="nomatch">
      <Header>404</Header>
      <p>Looks like you stumbled on an empty page.</p>
    </div>
  );
};

export default BasicNoMatchComponent;
