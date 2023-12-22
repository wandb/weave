import {
  constNodeUnsafe,
  constString,
  defaultLanguageBinding,
  escapeDots,
  isAssignableTo,
  isObjectType,
  isObjectTypeLike,
  isTypedDictLike,
  Node,
  nonNullable,
  opIsNone,
  opObjGetAttr,
  opPick as actualOpPick,
  Type,
  typedDict,
  typedDictPropertyTypes,
  TypedDictType,
  unionObjectTypeAttrTypes,
  varNode,
} from '@wandb/weave/core';
import {useNodeValue} from '@wandb/weave/react';
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';
import {Icon} from 'semantic-ui-react';

import {useWeaveContext} from '../../context';
import {ChildPanel} from './ChildPanel';
import * as ConfigPanel from './ConfigPanel';
import * as KeyValTable from './KeyValTable';
import * as Panel2 from './panel';
import {Spec as PanelDateSpec} from './PanelDate';
import PanelDate from './PanelDate/Component';
import {PanelNumber, Spec as PanelNumberSpec} from './PanelNumber';
import {PanelString, Spec as PanelStringSpec} from './PanelString';

const inputType = {
  type: 'union' as const,
  members: [
    {type: 'typedDict' as const, propertyTypes: {}},
    {type: 'Object' as const, _is_object: true as const},
  ],
};

export interface ObjectConfig {
  propLimit?: number;
  expanded?: boolean;
  children: {[key: string]: any};
}

type PanelObjectProps = Panel2.PanelProps<typeof inputType, ObjectConfig> & {
  level?: number;
};

const PanelObjectConfig: React.FC<PanelObjectProps> = props => {
  const {config, updateConfig} = props;
  const updateLimit = useCallback(
    (propLimit: number) => {
      updateConfig({
        ...config,
        propLimit,
      });
    },
    [updateConfig, config]
  );

  return (
    <ConfigPanel.ConfigOption label={'Field limit'}>
      <ConfigPanel.ModifiedDropdownConfigField
        selection
        allowAdditions
        options={[
          {
            text: '10',
            value: 10,
          },
          {
            text: '50',
            value: 50,
          },
          {
            text: '100',
            value: 100,
          },
          {
            text: '200',
            value: 200,
          },
          {
            text: '500',
            value: 500,
          },
          {
            text: 'No limit',
            value: Infinity,
          },
        ]}
        value={config?.propLimit ?? 100}
        onChange={(e, {value}) => {
          let newValue = Math.max(1, Number(value));
          if (isNaN(newValue)) {
            newValue = 1;
          }
          updateLimit(newValue);
        }}
      />
    </ConfigPanel.ConfigOption>
  );
};
const typeIsRenderableByPanelObject = (type: Type): boolean => {
  type = nonNullable(type);
  return isTypedDictLike(type) || isObjectTypeLike(type);
};

export const PanelObject: React.FC<PanelObjectProps> = props => {
  const {config, updateConfig} = props;
  const level = props.level ?? 0;
  const weave = useWeaveContext();
  const {updateInput: updateInputFromProps} = props;
  const nonNullableInput = nonNullable(props.input.type);

  const inputVar = useMemo(
    () => varNode(props.input.type, 'input'),
    [props.input.type]
  );

  // This is needed because dict(str, Any) is assignable to the input type
  // of this panel, but we cant render that with a PanelObject at the moment
  // so we have this more restrictive type checker to ensure we do not try to
  // render dicts the same way that we would render true typedDicts.

  const {objPropTypes, pickOrGetattr} = useMemo(() => {
    if (isTypedDictLike(nonNullableInput)) {
      return {
        objPropTypes: typedDictPropertyTypes(nonNullableInput),
        pickOrGetattr: (objNode: Node, key: string) => {
          if (
            objNode.nodeType === 'const' &&
            isAssignableTo(objNode.type, typedDict({[key]: 'any'}))
          ) {
            // If the node is a const, we can improve performance (e.g. in panelplot tooltips)
            // by just doing the pick off the value directly and saving a network request

            const type = objNode.type as TypedDictType;
            const {val} = objNode;
            if (
              val != null &&
              _.isPlainObject(val) &&
              val.hasOwnProperty(key)
            ) {
              const keyType = type.propertyTypes[key];
              if (keyType != null) {
                return constNodeUnsafe(keyType, val[key]);
              }
            }
          }
          return actualOpPick({obj: objNode, key: constString(key)});
        },
      };
    } else if (isObjectTypeLike(nonNullableInput)) {
      return {
        objPropTypes: unionObjectTypeAttrTypes(nonNullableInput),
        pickOrGetattr: (objNode: Node, key: string) =>
          opObjGetAttr({self: objNode, name: constString(key)}),
      };
    } else {
      // Unions are not supported, but we should not error
      return {
        objPropTypes: {},
        pickOrGetattr: (objNode: Node, key: string) => {
          throw new Error('Invalid input type');
        },
      };
    }
  }, [nonNullableInput]);
  const propertyTypes = _.mapKeys(objPropTypes, (v, k) => escapeDots(k));

  const propLimit = props.config?.propLimit ?? 100;

  const keys = useMemo(() => {
    const allKeys = Object.keys(propertyTypes);
    if (allKeys.length > propLimit) {
      return allKeys.slice(0, propLimit);
    } else {
      return allKeys;
    }
  }, [propLimit, propertyTypes]);

  const updateInput = useCallback(
    (key, newInput) => {
      if (newInput == null) {
        return updateInputFromProps?.(pickOrGetattr(inputVar, key) as any);
      } else {
        const input = pickOrGetattr(inputVar, key);
        const innerFunction = weave.callFunction((newInput as any).path, {
          input,
        });
        return updateInputFromProps?.(innerFunction as any);
      }
    },
    [inputVar, pickOrGetattr, updateInputFromProps, weave]
  );

  const keyChildren = useMemo(
    () =>
      _.sortBy(keys, k => {
        const kType = nonNullable(propertyTypes[k]!);
        return isAssignableTo(kType, PanelStringSpec.inputType) ||
          isAssignableTo(kType, PanelNumberSpec.inputType) ||
          isAssignableTo(kType, PanelDateSpec.inputType) ||
          typeIsRenderableByPanelObject(kType)
          ? 0
          : 1;
      }).map(k => {
        const childNode = pickOrGetattr(props.input, k);
        return (
          <PanelObjectChild
            key={k}
            {...props}
            k={k}
            level={level}
            childNode={childNode}
            childType={propertyTypes[k]!}
            updateInput={updateInputFromProps == null ? undefined : updateInput}
          />
        );
      }),
    [
      keys,
      level,
      pickOrGetattr,
      propertyTypes,
      props,
      updateInput,
      updateInputFromProps,
    ]
  );
  const defaultExpanded = !isObjectType(nonNullableInput) || level === 0;
  const expanded = props.config?.expanded ?? defaultExpanded;

  const toggleExpanded = useCallback(() => {
    updateConfig({
      ...config,
      expanded: !expanded,
    });
  }, [updateConfig, config, expanded]);

  return (
    <div
      style={{
        width: '100%',
        height: '100%',
        overflowY: 'auto',
        paddingLeft: level === 0 ? '8px' : '0px',
        paddingBottom: level === 0 ? '4px' : '0px',
      }}>
      <div style={{display: 'table', fontSize: '13px'}}>
        {isObjectType(nonNullableInput) && (
          <div
            style={{display: 'flex', alignItems: 'center'}}
            onClick={() => toggleExpanded()}>
            <Icon size="mini" name={`chevron ${expanded ? 'down' : 'right'}`} />
            {nonNullableInput.type}
          </div>
        )}
        {expanded && <KeyValTable.Rows>{keyChildren}</KeyValTable.Rows>}
      </div>
    </div>
  );
};

const PanelObjectChild: React.FC<
  {
    k: string;
    level: number;
    childNode: Node;
    childType: Type;
    updateInput?: (key: any, newInput: any) => void;
  } & Omit<PanelObjectProps, 'updateInput'>
> = ({
  k,
  level,
  childNode,
  childType,
  updateInput,
  context,
  updateContext,
  updateConfig,
  config,
}) => {
  const nonNullableChildType = nonNullable(childType);
  let isNone = useNodeValue(opIsNone({val: childNode}), {
    skip: childNode.nodeType === 'const',
  });

  if (childNode.nodeType === 'const') {
    isNone = {loading: false, result: childNode.val == null};
  }

  if (isNone.loading || isNone.result) {
    return null;
  }

  return (
    <KeyValTable.Row>
      <KeyValTable.Key>
        {updateInput == null ? (
          k
        ) : (
          <KeyValTable.InputUpdateLink onClick={() => updateInput(k, null)}>
            {k}
          </KeyValTable.InputUpdateLink>
        )}
      </KeyValTable.Key>
      <KeyValTable.Val>
        {isAssignableTo(nonNullableChildType, PanelNumberSpec.inputType) ? (
          <div style={{padding: '0px 1em'}}>
            <PanelNumber
              input={childNode as any}
              context={context}
              updateContext={updateContext}
              // Get rid of updateConfig
              updateConfig={() => {}}
              textAlign="left"
            />
          </div>
        ) : isAssignableTo(nonNullableChildType, PanelStringSpec.inputType) ? (
          <PanelString
            input={childNode as any}
            context={context}
            updateContext={updateContext}
            // Get rid of updateConfig
            updateConfig={() => {}}
          />
        ) : isAssignableTo(nonNullableChildType, PanelDateSpec.inputType) ? (
          <PanelDate
            input={childNode as any}
            context={context}
            updateContext={updateContext}
            // Get rid of updateConfig
            updateConfig={() => {}}
          />
        ) : typeIsRenderableByPanelObject(nonNullableChildType) ? (
          <div style={{paddingLeft: '1em', paddingTop: '1em'}}>
            <PanelObject
              input={childNode as any}
              level={level + 1}
              config={config?.children?.[k]}
              context={context}
              updateContext={updateContext}
              // Get rid of updateConfig
              updateConfig={newChildConfig =>
                updateConfig({
                  ...config,
                  children: {
                    ...config?.children,
                    [k]: newChildConfig,
                  },
                })
              }
              updateInput={
                updateInput == null
                  ? undefined
                  : newInput => updateInput(k, newInput)
              }
            />
          </div>
        ) : (
          <div style={{paddingLeft: '1em', height: 400, width: '100%'}}>
            {defaultLanguageBinding.printType(childType, true)}
            {/* TODO: This is not probably what we always want! - came from weaveflow */}
            <ChildPanel
              config={config?.children?.[k] ?? childNode}
              updateConfig={newConfig => {
                updateConfig({
                  ...config,
                  children: {
                    ...config?.children,
                    [k]: newConfig,
                  },
                });
              }}
            />
          </div>
        )}
      </KeyValTable.Val>
    </KeyValTable.Row>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'object',
  icon: 'list-bullets',
  Component: PanelObject,
  ConfigComponent: PanelObjectConfig,
  inputType,
};
