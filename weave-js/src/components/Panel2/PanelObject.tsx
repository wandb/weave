import {
  constString,
  defaultLanguageBinding,
  escapeDots,
  isAssignableTo,
  opPick,
  typedDictPropertyTypes,
  varNode,
} from '@wandb/weave/core';
import _ from 'lodash';
import React, {useCallback, useMemo} from 'react';

import {useWeaveContext} from '../../context';
import * as ConfigPanel from './ConfigPanel';
import * as KeyValTable from './KeyValTable';
import * as Panel2 from './panel';
import {Spec as PanelDateSpec} from './PanelDate';
import PanelDate from './PanelDate/Component';
import {PanelNumber, Spec as PanelNumberSpec} from './PanelNumber';
import {PanelString, Spec as PanelStringSpec} from './PanelString';

const inputType = {type: 'typedDict' as const, propertyTypes: {}};

export interface ObjectConfig {
  propLimit?: number;
}

type PanelObjectProps = Panel2.PanelProps<typeof inputType, ObjectConfig>;

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
  const weave = useWeaveContext();
  const {updateInput: updateInputFromProps} = props;

  const inputVar = useMemo(
    () => varNode(props.input.type, 'input'),
    [props.input.type]
  );

  const propertyTypes = _.mapKeys(
    typedDictPropertyTypes(props.input.type),
    (v, k) => escapeDots(k)
  );

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
        return updateInputFromProps?.(
          opPick({
            obj: inputVar,
            key: constString(key),
          }) as any
        );
      } else {
        const input = opPick({
          obj: inputVar,
          key: constString(key),
        });
        const innerFunction = weave.callFunction((newInput as any).path, {
          input,
        });
        return updateInputFromProps?.(innerFunction as any);
      }
    },
    [inputVar, updateInputFromProps, weave]
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
                input={
                  opPick({
                    obj: props.input,
                    key: constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : isAssignableTo(propertyTypes[k]!, PanelNumberSpec.inputType) ? (
              <PanelNumber
                input={
                  opPick({
                    obj: props.input,
                    key: constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : isAssignableTo(propertyTypes[k]!, PanelDateSpec.inputType) ? (
              <PanelDate
                input={
                  opPick({
                    obj: props.input,
                    key: constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : isAssignableTo(propertyTypes[k]!, Spec.inputType) ? (
              <PanelObject
                input={
                  opPick({
                    obj: props.input,
                    key: constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
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
      propertyTypes,
      props.context,
      props.input,
      props.updateContext,
      updateInput,
    ]
  );

  return (
    <KeyValTable.Table>
      <tbody>{keyChildren}</tbody>
    </KeyValTable.Table>
  );
};

export const Spec: Panel2.PanelSpec = {
  id: 'object',
  Component: PanelObject,
  ConfigComponent: PanelObjectConfig,
  inputType,
};
