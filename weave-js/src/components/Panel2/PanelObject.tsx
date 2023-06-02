import React, {useCallback, useMemo} from 'react';
import _ from 'lodash';

import {
  constString,
  defaultLanguageBinding,
  escapeDots,
  isAssignableTo,
  isTypedDictLike,
  opObjGetAttr,
  opPick as actualOpPick,
  typedDictPropertyTypes,
  varNode,
  NodeOrVoidNode,
  isObjectType,
} from '@wandb/weave/core';

import {Icon} from 'semantic-ui-react';
import {useWeaveContext} from '../../context';
import * as Panel2 from './panel';
import * as KeyValTable from './KeyValTable';
import {PanelString, Spec as PanelStringSpec} from './PanelString';
import {PanelNumber, Spec as PanelNumberSpec} from './PanelNumber';
import {Spec as PanelDateSpec} from './PanelDate';
import PanelDate from './PanelDate/Component';
import * as ConfigPanel from './ConfigPanel';

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
export const PanelObject: React.FC<PanelObjectProps> = props => {
  const level = props.level ?? 0;
  const weave = useWeaveContext();
  const {updateInput: updateInputFromProps} = props;

  const inputVar = useMemo(
    () => varNode(props.input.type, 'input'),
    [props.input.type]
  );

  const isTypedDict = isTypedDictLike(props.input.type);
  const propTypes = isTypedDict
    ? typedDictPropertyTypes(props.input.type)
    : _.fromPairs(
        Object.keys(props.input.type)
          .filter(k => !k.startsWith('_') && k !== 'type')
          .map(k => [k, props.input.type[k]])
      );
  const propertyTypes = _.mapKeys(propTypes, (v, k) => escapeDots(k));

  const pick = (objNode: Node, key: string) => {
    return isTypedDict
      ? actualOpPick({obj: objNode, key: constString(key)})
      : opObjGetAttr({self: objNode, name: constString(key)});
  };

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
      console.log('UPDATE INPUT', key);
      if (newInput == null) {
        return updateInputFromProps?.(pick(inputVar, key) as any);
      } else {
        const input = pick(inputVar, constString(key));
        const innerFunction = weave.callFunction((newInput as any).path, {
          input,
        });
        return updateInputFromProps?.(innerFunction as any);
      }
    },
    [inputVar, pick, updateInputFromProps, weave]
  );

  const keyChildren = useMemo(
    () =>
      keys.map(k => (
        <KeyValTable.Row key={k}>
          <KeyValTable.Key>
            <KeyValTable.InputUpdateLink onClick={() => updateInput(k, null)}>
              {k}
            </KeyValTable.InputUpdateLink>
          </KeyValTable.Key>
          <KeyValTable.Val>
            {isAssignableTo(propertyTypes[k]!, PanelStringSpec.inputType) ? (
              <PanelString
                input={pick(props.input, k) as any}
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : isAssignableTo(propertyTypes[k]!, PanelNumberSpec.inputType) ? (
              <PanelNumber
                input={pick(props.input, k) as any}
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : isAssignableTo(propertyTypes[k]!, PanelDateSpec.inputType) ? (
              <PanelDate
                input={pick(props.input, k) as any}
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : isAssignableTo(propertyTypes[k]!, Spec.inputType) ? (
              <PanelObject
                input={pick(props.input, k) as any}
                level={level + 1}
                config={props.config?.children?.[k]}
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={newChildConfig =>
                  props.updateConfig({
                    ...props.config,
                    children: {...props.config?.children, [k]: newChildConfig},
                  })
                }
                updateInput={newInput => updateInput(k, newInput)}
              />
            ) : (
              <div>
                {defaultLanguageBinding.printType(propertyTypes[k]!, true)}
              </div>
            )}
          </KeyValTable.Val>
        </KeyValTable.Row>
      )),
    [
      keys,
      pick,
      propertyTypes,
      props.context,
      props.input,
      props.updateContext,
      updateInput,
    ]
  );
  const defaultExpanded = !isObjectType(props.input.type) || level === 0;
  const expanded = props.config?.expanded ?? defaultExpanded;

  const toggleExpanded = useCallback(() => {
    props.updateConfig({
      ...props.config,
      expanded: !expanded,
    });
  }, [props.updateConfig, props.config, expanded]);

  return (
    <KeyValTable.Table>
      {isObjectType(props.input.type) && (
        <div
          style={{display: 'flex', alignItems: 'center'}}
          onClick={() => toggleExpanded()}>
          <Icon size="mini" name={`chevron ${expanded ? 'down' : 'right'}`} />
          {props.input.type.type}
        </div>
      )}
      {expanded && <tbody>{keyChildren}</tbody>}
    </KeyValTable.Table>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'object',
  Component: PanelObject,
  ConfigComponent: PanelObjectConfig,
  inputType,
};
