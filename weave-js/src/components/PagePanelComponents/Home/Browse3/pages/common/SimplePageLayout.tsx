import MoreVertIcon from '@mui/icons-material/MoreVert';
import {Box, ListItemText, MenuList, Tab, Tabs} from '@mui/material';
// import {Menu} from '@mui/base/Menu';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import _ from 'lodash';
import React, {
  createContext,
  CSSProperties,
  FC,
  MouseEvent,
  ReactNode,
  SyntheticEvent,
  useContext,
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
  menuItems?: Array<{
    label: string;
    onClick: () => void;
  }>;
  leftSidebar?: ReactNode;
  hideTabsIfSingle?: boolean;
}> = props => {
  const simplePageLayoutContextValue = useContext(SimplePageLayoutContext);
  const [tabId, setTabId] = useState(0);
  const handleTabChange = (event: SyntheticEvent, newValue: number) => {
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
        overflow: 'hidden',
      }}>
      <Box
        sx={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          backgroundColor: 'white',
          pb: 0,
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
            height: 65, // manual to match sidebar
            flex: '0 0 65px',
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
          <Box
            sx={{
              flex: '0 0 auto',
            }}>
            {props.menuItems && <ActionMenu menuItems={props.menuItems} />}
          </Box>
          {simplePageLayoutContextValue.headerSuffix}
        </Box>
        {(!props.hideTabsIfSingle || props.tabs.length > 1) && (
          <Tabs
            variant="scrollable"
            scrollButtons="auto"
            value={tabId}
            onChange={handleTabChange}>
            {props.tabs.map((tab, i) => (
              <Tab key={i} label={tab.label} />
            ))}
          </Tabs>
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
  title: string;
  tabs: Array<{
    label: string;
    content: ReactNode;
  }>;
  menuItems?: Array<{
    label: string;
    onClick: () => void;
  }>;
  headerExtra?: ReactNode;
  headerContent: ReactNode;
  leftSidebar?: ReactNode;
  hideTabsIfSingle?: boolean;
  isSidebarOpen?: boolean;
}> = props => {
  const simplePageLayoutContextValue = useContext(SimplePageLayoutContext);
  const [tabId, setTabId] = useState(0);
  const handleTabChange = (event: SyntheticEvent, newValue: number) => {
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
          height: 65, // manual to match sidebar
          flex: '0 0 65px',
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'flex-end',
          gap: 1,
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
        <Box
          sx={{
            flex: '0 0 auto',
          }}>
          {props.menuItems && <ActionMenu menuItems={props.menuItems} />}
        </Box>
        {props.headerExtra}
        {simplePageLayoutContextValue.headerSuffix}
      </Box>
      <div style={{marginLeft: 4, flex: '1 1 auto', overflow: 'hidden'}}>
        <SplitPanel
          minWidth={150}
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
                }}>
                {props.headerContent}
              </Box>
              {(!props.hideTabsIfSingle || props.tabs.length > 1) && (
                <Tabs
                  style={{
                    borderBottom: '1px solid #e0e0e0',
                  }}
                  variant="scrollable"
                  // These scroll buttons are not working
                  scrollButtons={false}
                  value={tabId}
                  onChange={handleTabChange}>
                  {props.tabs.map((tab, i) => (
                    <Tab key={i} label={tab.label} />
                  ))}
                </Tabs>
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

const ActionMenu: FC<{
  menuItems: Array<{
    label: string;
    onClick: () => void;
  }>;
}> = props => {
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const handleClick = (event: MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <Box
      sx={{
        height: '47px',
        flex: '0 0 auto',
      }}>
      <IconButton
        aria-label="more"
        id="long-button"
        aria-controls={open ? 'long-menu' : undefined}
        aria-expanded={open ? 'true' : undefined}
        aria-haspopup="true"
        onClick={handleClick}>
        <MoreVertIcon />
      </IconButton>
      <Menu anchorEl={anchorEl} open={open} onClose={handleClose}>
        <Box sx={{width: 320, maxWidth: '100%'}}>
          <MenuList>
            {props.menuItems.map((item, i) => (
              <MenuItem
                key={i}
                onClick={() => {
                  handleClose();
                  item.onClick();
                }}>
                <ListItemText>{item.label}</ListItemText>
              </MenuItem>
            ))}
          </MenuList>
        </Box>
      </Menu>
    </Box>
  );
};

export const ScrollableTabContent: FC<{
  sx?: CSSProperties;
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
