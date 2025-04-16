import {Box, SxProps, Theme} from '@mui/material';
import {MOON_200} from '@wandb/weave/common/css/color.styles';
import {IconName} from '@wandb/weave/components/Icon';
import * as Tabs from '@wandb/weave/components/Tabs';
import _ from 'lodash';
import React, {
  createContext,
  FC,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import {ErrorBoundary} from '../../../../../ErrorBoundary';
import {SplitPanelLeft} from './SplitPanels/SplitPanelLeft';
import {SplitPanelRight} from './SplitPanels/SplitPanelRight';
import {isPrimitive} from './util';

type SimplePageLayoutContextType = {
  headerPrefix?: ReactNode;
  headerSuffix?: ReactNode;
};

export const SimplePageLayoutContext =
  createContext<SimplePageLayoutContextType>({});

export const SimplePageLayout: FC<{
  title: React.ReactNode;
  tabs: Array<{
    label: string;
    content: ReactNode;
  }>;
  leftSidebarContent?: ReactNode;
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
          height: 44,
          width: '100%',
          borderBottom: `1px solid ${MOON_200}`,
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          flex: '0 0 auto',
        }}>
        <Box
          sx={{
            height: 44,
            flex: '1 0 44px',
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'center',
            gap: 1,
            pl: 2,
            pr: 2,
          }}>
          {simplePageLayoutContextValue.headerPrefix}
          <Box
            sx={{
              fontWeight: 600,
              fontSize: '1.25rem',
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
        {props.leftSidebarContent && (
          <Box
            sx={{
              width: '35%',
              flex: '0 0 35%',
              overflow: 'hidden',
              height: '100%',
              maxHeight: '100%',
              borderRight: `1px solid ${MOON_200}`,
            }}>
            {props.leftSidebarContent}
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
  title?: ReactNode;
  tabs: Array<{
    label: string;
    icon?: IconName;
    content: ReactNode;
  }>;
  headerExtra?: ReactNode;
  headerContent: ReactNode;
  hideTabsIfSingle?: boolean;
  onTabSelectedCallback?: (tab: string) => void;
  // Left sidebar
  isLeftSidebarOpen?: boolean;
  leftSidebarContent?: ReactNode;
  // Right sidebar
  isRightSidebarOpen?: boolean;
  rightSidebarContent?: ReactNode;
  dimMainContent?: boolean;
}> = props => {
  const {tabs} = props;
  const simplePageLayoutContextValue = useContext(SimplePageLayoutContext);

  // We try to preserve the selected tab even if the set of tabs changes,
  // falling back to the first tab.
  const [tabId, setTabId] = useState(tabs[0].label);
  const setAndNotifyTab = useCallback(
    (newValue: string) => {
      setTabId(newValue);
      props.onTabSelectedCallback?.(newValue);
    },
    [props]
  );
  // If the user has manually selected a tab, always keep that tab selected
  // otherwise, always default to the leftmost tab. Some calls have chat
  // tabs, others do not, so unless the user has explicitly selected a different
  // tab, always show the chat tab when possible.
  const [userSelectedTab, setUserSelectedTab] = useState(false);
  const idxSelected = tabs.findIndex(t => t.label === tabId);
  const tabValue = idxSelected !== -1 ? idxSelected : 0;
  const handleTabChange = (newValue: string) => {
    setAndNotifyTab(newValue);
    setUserSelectedTab(true);
  };
  useEffect(() => {
    if (idxSelected === -1) {
      setAndNotifyTab(tabs[0].label);
      setUserSelectedTab(false);
    } else if (!userSelectedTab && idxSelected === 1) {
      // User has not selected a tab, but the current tab is not the leftmost tab.
      // Default to the leftmost.
      // Example: view call w/o chat [tab='call'] -> view call w/ chat [tab='call']
      setAndNotifyTab(tabs[0].label);
    }
  }, [tabs, idxSelected, userSelectedTab, setAndNotifyTab]);
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
          height: 44,
          width: '100%',
          flex: '0 0 44px',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          pl: 2,
          pr: 2,
          // merge line
          position: 'sticky',
          top: 0,
          zIndex: 1,
          backgroundColor: 'white',
          pb: 0,
          borderBottom: `1px solid ${MOON_200}`,
          justifyContent: 'flex-start',
        }}>
        {simplePageLayoutContextValue.headerPrefix}
        <Box
          sx={{
            fontWeight: 600,
            fontSize: '1.25rem',
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
        <SplitPanelLeft
          minWidth={150}
          defaultWidth={400}
          maxWidth="50%"
          isDrawerOpen={props.isLeftSidebarOpen ?? false}
          drawer={props.leftSidebarContent}
          main={
            <SplitPanelRight
              minWidth={150}
              defaultWidth={200}
              maxWidth="50%"
              drawer={props.rightSidebarContent}
              isDrawerOpen={props.isRightSidebarOpen ?? false}
              style={{
                opacity: props.dimMainContent ? 0.5 : 1,
                transition: 'opacity 0.3s ease-in-out',
                // Disable pointer events
                pointerEvents: props.dimMainContent ? 'none' : 'auto',
              }}
              main={
                <SimpleTabView
                  headerContent={props.headerContent}
                  tabContent={tabContent}
                  tabs={props.tabs}
                  tabId={tabId}
                  tabValue={tabValue}
                  hideTabsIfSingle={props.hideTabsIfSingle}
                  handleTabChange={handleTabChange}
                />
              }
            />
          }
        />
      </div>
    </Box>
  );
};

const SimpleTabView: FC<{
  headerContent: ReactNode;
  tabs: Array<{
    label: string;
    content: ReactNode;
  }>;
  tabContent: ReactNode;
  tabId: string;
  tabValue: number;
  hideTabsIfSingle?: boolean;
  handleTabChange: (newValue: string) => void;
}> = props => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        flexGrow: 1,
        height: '100%',
        overflow: 'hidden',
      }}>
      {props.headerContent && (
        <Box
          sx={{
            maxHeight: '50%',
            flex: '0 0 auto',
            width: '100%',
            overflow: 'auto',
            pt: 1,
            px: 2,
            alignContent: 'center',
          }}>
          {props.headerContent}
        </Box>
      )}
      {(!props.hideTabsIfSingle || props.tabs.length > 1) && (
        <Tabs.Root
          style={{margin: '12px 16px 0 16px'}}
          value={props.tabs[props.tabValue].label}
          onValueChange={props.handleTabChange}>
          <Tabs.List style={{overflowX: 'scroll', scrollbarWidth: 'none'}}>
            {props.tabs.map(tab => (
              <Tabs.Trigger
                key={tab.label}
                value={tab.label}
                className="h-[30px] whitespace-nowrap text-sm">
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
        <ErrorBoundary key={props.tabId}>{props.tabContent}</ErrorBoundary>
      </Box>
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
  keyColumnWidth?: string | number;
}> = props => {
  return (
    <div className="w-full overflow-hidden rounded border border-[#E0E0E0]">
      <table className="w-full text-[14px]">
        <tbody className="divide-y divide-[#E0E0E0]">
          {Object.entries(props.data).map(([key, val]) => {
            return (
              <tr key={key}>
                <td
                  className="border-r border-[#E0E0E0] bg-moon-50 p-[8px] align-top text-moon-500"
                  style={
                    props.keyColumnWidth
                      ? {width: props.keyColumnWidth}
                      : undefined
                  }>
                  {key}
                </td>
                <td className="p-[8px] align-top">
                  {isPrimitive(val) ? (
                    val
                  ) : _.isArray(val) ? (
                    <SimpleKeyValueTable
                      data={_.fromPairs(val.map((v, i) => [i, v]))}
                      keyColumnWidth={props.keyColumnWidth}
                    />
                  ) : (
                    <SimpleKeyValueTable
                      data={_.fromPairs(Object.entries(val as any))}
                      keyColumnWidth={props.keyColumnWidth}
                    />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
