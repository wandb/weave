import {Box, Tab, Tabs} from '@mui/material';
import React, {useMemo} from 'react';

import {ErrorBoundary} from '../../../../../ErrorBoundary';

export const SimplePageLayout: React.FC<{
  title: string;
  tabs: Array<{
    label: string;
    content: React.ReactNode;
  }>;
}> = props => {
  const [tabId, setTabId] = React.useState(0);
  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setTabId(newValue);
  };
  const tabContent = useMemo(
    () => props.tabs[tabId].content,
    [props.tabs, tabId]
  );
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        height: '100%',
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          backgroundColor: 'white',
          pb: 0,
          pl: 3,
          pr: 3,
          height: 65, // manual to match sidebar
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          flex: '0 0 auto',
        }}>
        <Box
          sx={{
            pb: 2,
            fontWeight: 600,
            fontSize: '1.5rem',
            flex: '0 0 auto',
            overflow: 'auto',
          }}>
          {props.title}
        </Box>
        <Tabs
          variant="scrollable"
          scrollButtons="auto"
          value={tabId}
          onChange={handleTabChange}>
          {props.tabs.map((tab, i) => (
            <Tab key={i} label={tab.label} />
          ))}
        </Tabs>
      </Box>
      <Box
        component="main"
        sx={{
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          flex: '1 1 auto',
        }}>
        <ErrorBoundary key={tabId}>{tabContent}</ErrorBoundary>
      </Box>
    </Box>
  );
};

export const ScrollableTabContent: React.FC<{
  sx?: React.CSSProperties;
}> = props => {
  return (
    <Box
      sx={{
        height: '100%',
        width: '100%',
        flexGrow: 1,
        overflow: 'auto',
        p: 2,
        ...(props.sx ?? {}),
      }}>
      {props.children}
    </Box>
  );
};

export const SimpleKeyValueTable: React.FC<{
  data: {[key: string]: React.ReactNode};
}> = props => {
  return (
    <table>
      <tbody>
        {Object.keys(props.data).map(key => (
          <tr key={key}>
            <td
              style={{
                fontWeight: 600,
                marginRight: 10,
                paddingRight: 10,

                // align text to the top
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'flex-start',
              }}>
              {key}
            </td>
            <td>{props.data[key]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};
