import {Node, Stack} from '@wandb/weave/core';
import React, {PropsWithChildren} from 'react';
import ReactDOM from 'react-dom';
import {Checkbox, Header, Icon, Menu, Ref} from 'semantic-ui-react';
import styled from 'styled-components';

import {usePanelContext} from '../components/Panel2/PanelContext';
import {useWeaveContext} from '../context';
import {useWeaveActionContext} from './context';
import {NodeAction} from './types';

const MenuWrapper = styled.div<{position: {x: number; y: number}}>`
  position: fixed;

  // So we have some extra margin around the popup
  // menu's visible area before it closes due to
  // mouse leaving
  padding: 8px;
  left: ${props => props.position.x - 8}px;
  top: ${props => props.position.y - 8}px;
  z-index: 20001;
  max-width: 300px;

  // Expression
  &&& pre {
    overflow-wrap: break-word;
    white-space: pre-wrap;
  }

  // Section headers
  &&& h4 {
    font-weight: 600;
    font-size: 1.1em;
    margin-block-end: 0.2em;
  }

  // Detail
  &&& p {
    font-family: monospace;
    margin-left: 2.2em;
  }

  &&& i.icon {
    font-size: 1em;
  }
`;
MenuWrapper.displayName = 'S.MenuWrapper';

const MiniExpression = styled.pre``;
MiniExpression.displayName = 'S.MiniExpression';

const SmallCheckbox = styled(Checkbox)`
  &&& {
    transform: scale(0.6);
    margin-left: -1.4em;
  }
`;
SmallCheckbox.displayName = 'S.SmallCheckbox';

interface MenuContentProps {
  // HTMLElement, or any other type that implements getBoundingClientRect
  // to position the menu
  anchor: Pick<HTMLElement, 'getBoundingClientRect'>;
  actions: NodeAction[];
  input: Node;
  stack: Stack;
  close: () => void;
}

// We remember last setting so new menus open in the same state
let lastDetailedSetting = false;

const ActionsContent: React.FC<MenuContentProps> = ({
  anchor,
  actions,
  input,
  stack,
  close,
}: MenuContentProps) => {
  const weave = useWeaveContext();

  const [detailed, setDetailed] = React.useState(lastDetailedSetting);
  const [position, setPosition] = React.useState<{x: number; y: number} | null>(
    null
  );

  const [items, setItems] = React.useState<
    Array<{label: string; description?: string; action: NodeAction}>
  >([]);

  React.useEffect(() => {
    const resolveActions = async () => {
      setItems(
        await Promise.all(
          actions.map(async action => {
            return {
              label:
                typeof action.name === 'function'
                  ? await action.name(input, stack)
                  : action.name,
              description:
                typeof action.detail === 'function'
                  ? await action.detail(input, stack)
                  : action.detail,
              action,
            };
          })
        )
      );
    };
    resolveActions();
  }, [actions, stack, input]);

  // TODO(np): These look terrible and not useful.
  // Fix truncation to show n tail nodes
  // Fix simple type output
  const expStr = React.useMemo(() => {
    let result = weave.expToString(input, null);
    if (!detailed && result.length > 40) {
      // Truncate to last 40 characters of result
      result = '...' + result.slice(-40);
    }
    return result;
  }, [weave, input, detailed]);

  const typeStr = React.useMemo(() => {
    return weave.typeToString(input.type, !detailed);
  }, [weave, input, detailed]);

  const [menuRef, setMenuRef] = React.useState<HTMLDivElement | null>(null);

  React.useEffect(() => {
    const {right, bottom} = anchor.getBoundingClientRect();
    const menuRect = menuRef?.getBoundingClientRect();
    if (!menuRect) {
      return;
    }
    const {width, height} = menuRect;

    // Avoid going off the right or bottom of the screen
    // This doesn't work well when the window is too small
    // to contain the menu
    let posX = right;
    let posY = bottom;
    if (posX > window.innerWidth - width) {
      posX = right - width;
    }
    if (posY > window.innerHeight - height) {
      posY = bottom - height;
    }
    setPosition({
      x: posX,
      y: posY,
    });
  }, [anchor, menuRef]);

  // Need to draw offscreen so we can measure and figure out
  // what position actually needs to be
  return ReactDOM.createPortal(
    <MenuWrapper
      position={position ?? {x: -10000, y: -10000}}
      onMouseLeave={close}>
      <Ref innerRef={setMenuRef}>
        <Menu vertical fluid size="mini">
          <Menu.Item fitted="vertically" position="right">
            <SmallCheckbox
              toggle
              checked={detailed}
              label="Detailed"
              onChange={(ev: React.FormEvent<HTMLInputElement>) => {
                lastDetailedSetting = !detailed;
                setDetailed(lastDetailedSetting);
              }}
            />
          </Menu.Item>
          <Menu.Item>
            <Menu.Header>Expression</Menu.Header>
            <MiniExpression>{expStr}</MiniExpression>
          </Menu.Item>
          <Menu.Item>
            <Menu.Header>Type</Menu.Header>
            <MiniExpression>{typeStr}</MiniExpression>
          </Menu.Item>
          <Menu.Item fitted="horizontally">
            <Menu.Header style={{paddingLeft: '1em'}}>Actions</Menu.Header>
            {items.length > 0 ? (
              items.map((item, idx) => {
                return (
                  <Menu.Item
                    name={item.label}
                    key={idx}
                    onMouseEnter={() =>
                      item.action.onHoverStart?.(input, stack)
                    }
                    onMouseLeave={() => item.action.onHoverEnd?.(input, stack)}
                    onClick={() => {
                      item.action.doAction(input, stack);
                      close();
                    }}>
                    <Header as="h4">
                      <Icon name={item.action.icon ?? 'bolt'} />
                      {item.label}
                    </Header>
                    {item.description != null ? (
                      <p>
                        <em>{item.description}</em>
                      </p>
                    ) : null}
                  </Menu.Item>
                );
              })
            ) : (
              <Menu.Item disabled>No actions available</Menu.Item>
            )}
          </Menu.Item>
        </Menu>
      </Ref>
    </MenuWrapper>,
    document.body
  );
};

type ActionsTriggerProps = React.PropsWithChildren<{
  input: Node;
  extraActions?: NodeAction[];
}>;

const InnerTriggerWrapper = styled.div`
  cursor: context-menu;
  width: 100%;
  height: 100%;
`;
InnerTriggerWrapper.displayName = 'S.InnerTriggerWrapper';

const TriggerWrapper: React.FC<
  PropsWithChildren<{onClick: React.MouseEventHandler}>
> = ({onClick, children}) => {
  return (
    <InnerTriggerWrapper onClick={onClick}>{children}</InnerTriggerWrapper>
  );
};

export const ActionsTrigger: React.FC<ActionsTriggerProps> = ({
  input,
  extraActions,
  children,
}: ActionsTriggerProps) => {
  const actionsContext = useWeaveActionContext();
  const {stack} = usePanelContext();

  const availableActions = React.useMemo(() => {
    const result = actionsContext.actions
      .concat(extraActions ?? [])
      .filter(action => action.isAvailable(input, stack));

    return result;
  }, [actionsContext.actions, extraActions, input, stack]);

  const [actionsVisible, setActionsVisible] = React.useState(false);
  const closeActions = React.useCallback(() => {
    setActionsVisible(false);
  }, []);

  // TODO: This looks a bit verbose but gives us the flexibility
  // to use any HTMLElement as an anchor later, even though we're
  // currently always opening at the cursor position
  const [anchor, setAnchor] = React.useState<Pick<
    HTMLElement,
    'getBoundingClientRect'
  > | null>(null);

  const toggleActions = React.useCallback(
    (ev: React.MouseEvent) => {
      ev.stopPropagation();

      setAnchor({
        getBoundingClientRect: () => ({
          left: ev.clientX,
          top: ev.clientY,
          right: ev.clientX + 1,
          bottom: ev.clientY + 1,

          x: ev.clientX,
          y: ev.clientY,
          height: 0,
          width: 0,
          toJSON() {
            throw new Error('Not implemented');
          },
        }),
      });
      setActionsVisible(!actionsVisible);
    },
    [actionsVisible]
  );

  return (
    <>
      <TriggerWrapper onClick={toggleActions}>{children}</TriggerWrapper>
      {actionsVisible && anchor != null && (
        <ActionsContent
          actions={availableActions}
          input={input}
          stack={stack}
          anchor={anchor}
          close={closeActions}
        />
      )}
    </>
  );
};
