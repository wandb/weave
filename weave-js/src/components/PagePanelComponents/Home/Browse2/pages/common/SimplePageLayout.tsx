import MoreVertIcon from '@mui/icons-material/MoreVert';
import {Box, ListItemText, MenuList, Tab, Tabs} from '@mui/material';
// import {Menu} from '@mui/base/Menu';
import IconButton from '@mui/material/IconButton';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import React, {useMemo} from 'react';

import {ErrorBoundary} from '../../../../../ErrorBoundary';

export const SimplePageLayout: React.FC<{
  title: string;
  tabs: Array<{
    label: string;
    content: React.ReactNode;
  }>;
  menuItems?: Array<{
    label: string;
    onClick: () => void;
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
            display: 'flex',
            flexDirection: 'row',
            alignItems: 'flex-end',
            gap: 1,
          }}>
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

const ActionMenu: React.FC<{
  menuItems: Array<{
    label: string;
    onClick: () => void;
  }>;
}> = props => {
  const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);
  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };
  const handleClose = () => {
    setAnchorEl(null);
  };

  return (
    <Box
      sx={{
        height: '47px',
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
