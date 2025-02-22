import React from 'react';

import {CallDetails} from '../../../CallPage/CallDetails';
import {CallViewProps} from '../../types';

export const DetailsView: React.FC<CallViewProps> = ({call}) => {
  return <CallDetails call={call} />;
};
