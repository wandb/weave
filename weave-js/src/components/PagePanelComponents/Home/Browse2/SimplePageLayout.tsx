import {Box, Tab, Tabs} from '@mui/material';
import React, {useMemo} from 'react';

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
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          pb: 0,
          pl: 3,
          pr: 3,
          height: 65, // manual to match sidebar
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
        }}>
        <Box
          sx={{
            pb: 2.5,
            fontWeight: 600,
            fontSize: '1.5rem',
          }}>
          {props.title}
        </Box>
        <Tabs value={tabId} onChange={handleTabChange}>
          {props.tabs.map((tab, i) => (
            <Tab key={i} label={tab.label} />
          ))}
        </Tabs>
      </Box>
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}>
        {tabContent}
      </Box>
    </Box>
  );
};
