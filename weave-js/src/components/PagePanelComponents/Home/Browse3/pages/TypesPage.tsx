import React, {useEffect} from 'react';
import {useHistory} from 'react-router-dom';

export const TypesPage: React.FC<{
  entity: string;
  project: string;
}> = props => {
  // TODO: Implement in due time if needed
  const history = useHistory();
  useEffect(() => {
    history.push(`/${props.entity}/${props.project}`);
  }, [history, props.entity, props.project]);
  return <></>;
};
