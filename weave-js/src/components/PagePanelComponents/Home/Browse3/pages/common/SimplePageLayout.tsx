import {Box, SxProps, Theme} from '@mui/material';
import * as Tabs from '@wandb/weave/components/Tabs';
import _ from 'lodash';
import React, {
  createContext,
  FC,
  ReactNode,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {SplitPanel} from './SplitPanel';
import {isPrimitive} from './util';

type SimplePageLayoutContextType = {
  headerPrefix?: ReactNode;
  headerSuffix?: ReactNode;
};

export const SimplePageLayoutContext =
  createContext<SimplePageLayoutContextType>({});

export const SimplePageLayout: FC<{
  title: string;
  tabs: Array<{
    label: string;
    content: ReactNode;
  }>;
  leftSidebar?: ReactNode;
  hideTabsIfSingle?: boolean;
  headerExtra?: ReactNode;
}> = props => {
  const {tabs} = props;
  const simplePageLayoutContextValue = useContext(SimplePageLayoutContext);

  // We try to preserve the selected tab even if the set of tabs changes,
  // falling back to the first tab.
  const [tabId, setTabId] = useState(tabs[0].label);
  const idxSelected = tabs.findIndex(t => t.label === tabId);
  const tabValue = idxSelected !== -1 ? idxSelected : 0;
  const handleTabChange = (newValue: string) => {
    setTabId(newValue);
  };
  useEffect(() => {
    if (idxSelected === -1) {
      setTabId(tabs[0].label);
    }
  }, [tabs, idxSelected]);
  const tabContent = useMemo(() => tabs[tabValue].content, [tabs, tabValue]);

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        height: '100%',
        overflow: 'hidden',
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          backgroundColor: 'white',
          pb: 0,
          height: 55, // manual to match sidebar

          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          flex: '0 0 auto',
        }}>
        <Box
          sx={{
            height: 55, // manual to match sidebar
            flex: '0 0 55px',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'flex-end',
            gap: 1,
            pl: 2,
            pr: 2,
          }}>
          {simplePageLayoutContextValue.headerPrefix}
          <Box
            sx={{
              pb: 2,
              fontWeight: 600,
              fontSize: '1.5rem',
              flex: '1 1 auto',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
            {props.title}
          </Box>
          {simplePageLayoutContextValue.headerSuffix}
        </Box>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'flex-end',
            flex: '0 0 auto',
          }}>
          {props.headerExtra}
        </Box>
        {(!props.hideTabsIfSingle || tabs.length > 1) && (
          <Tabs.Root
            value={tabs[tabValue].label}
            onValueChange={handleTabChange}>
            <Tabs.List>
              {tabs.map(tab => (
                <Tabs.Trigger key={tab.label} value={tab.label}>
                  {tab.label}
                </Tabs.Trigger>
              ))}
            </Tabs.List>
          </Tabs.Root>
        )}
      </Box>
      <Box
        sx={{
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'row',
          flex: '1 1 auto',
        }}>
        {props.leftSidebar && (
          <Box
            sx={{
              width: '35%',
              flex: '0 0 35%',
              overflow: 'hidden',
              height: '100%',
              maxHeight: '100%',
              borderRight: '1px solid #e0e0e0',
            }}>
            {props.leftSidebar}
          </Box>
        )}
        <Box
          sx={{
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            flex: '1 1 auto',
          }}>
          <ErrorBoundary key={tabId}>{tabContent}</ErrorBoundary>
        </Box>
      </Box>
    </Box>
  );
};

export const SimplePageLayoutWithHeader: FC<{
  title?: string;
  tabs: Array<{
    label: string;
    content: ReactNode;
  }>;
  headerExtra?: ReactNode;
  headerContent: ReactNode;
  leftSidebar?: ReactNode;
  hideTabsIfSingle?: boolean;
  isSidebarOpen?: boolean;
}> = props => {
  const {tabs} = props;
  const simplePageLayoutContextValue = useContext(SimplePageLayoutContext);

  // We try to preserve the selected tab even if the set of tabs changes,
  // falling back to the first tab.
  const [tabId, setTabId] = useState(tabs[0].label);
  const idxSelected = tabs.findIndex(t => t.label === tabId);
  const tabValue = idxSelected !== -1 ? idxSelected : 0;
  const handleTabChange = (newValue: string) => {
    setTabId(newValue);
  };
  useEffect(() => {
    if (idxSelected === -1) {
      setTabId(tabs[0].label);
    }
  }, [tabs, idxSelected]);
  const tabContent = useMemo(() => tabs[tabValue].content, [tabs, tabValue]);

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
          height: 55, // manual to match sidebar
          flex: '0 0 55px',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-end',
          pl: 2,
          pr: 2,
          // merge line
          position: 'sticky',
          top: 0,
          zIndex: 1,
          backgroundColor: 'white',
          pb: 0,
          borderBottom: '1px solid #e0e0e0',
          justifyContent: 'flex-start',
        }}>
        {simplePageLayoutContextValue.headerPrefix}
        <Box
          sx={{
            pb: 2,
            fontWeight: 600,
            fontSize: '1.5rem',
            flex: '1 1 auto',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}>
          {props.title}
        </Box>
        {props.headerExtra}
        {simplePageLayoutContextValue.headerSuffix}
      </Box>
      <div style={{flex: '1 1 auto', overflow: 'hidden'}}>
        <SplitPanel
          minWidth={150}
          defaultWidth={200}
          maxWidth="50%"
          isDrawerOpen={props.isSidebarOpen ?? false}
          drawer={props.leftSidebar}
          main={
            <Box
              sx={{
                display: 'flex',
                flexDirection: 'column',
                flexGrow: 1,
                height: '100%',
                overflow: 'hidden',
              }}>
              <Box
                sx={{
                  maxHeight: '50%',
                  flex: '0 0 auto',
                  width: '100%',
                  overflow: 'auto',
                  borderBottom: '1px solid #e0e0e0',
                  p: 1,
                  alignContent: 'center',
                }}>
                {props.headerContent}
              </Box>
              {(!props.hideTabsIfSingle || tabs.length > 1) && (
                <Tabs.Root
                  style={{margin: '12px 8px 0 8px'}}
                  value={tabs[tabValue].label}
                  onValueChange={handleTabChange}>
                  <Tabs.List>
                    {tabs.map(tab => (
                      <Tabs.Trigger key={tab.label} value={tab.label}>
                        {tab.label}
                      </Tabs.Trigger>
                    ))}
                  </Tabs.List>
                </Tabs.Root>
              )}
              <Box
                sx={{
                  overflow: 'hidden',
                  display: 'flex',
                  flexDirection: 'column',
                  flex: '1 1 auto',
                }}>
                <ErrorBoundary key={tabId}>{tabContent}</ErrorBoundary>
              </Box>
            </Box>
          }
        />
      </div>
    </Box>
  );
};

export const ScrollableTabContent: FC<{
  sx?: SxProps<Theme>;
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

export const SimpleKeyValueTable: FC<{
  data: {[key: string]: ReactNode};
}> = props => {
  return (
    <table
      style={{
        borderCollapse: 'collapse',
      }}>
      <tbody>
        {Object.entries(props.data).map(([key, val]) => {
          return (
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
              <td>
                {isPrimitive(val) ? (
                  val
                ) : _.isArray(val) ? (
                  <SimpleKeyValueTable
                    data={_.fromPairs(val.map((v, i) => [i, v]))}
                  />
                ) : (
                  <SimpleKeyValueTable
                    data={_.fromPairs(Object.entries(val as any))}
                  />
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
};
