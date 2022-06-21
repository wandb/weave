import React, {useCallback, useMemo, useEffect, useState} from 'react';
import _ from 'lodash';

import * as Op from '@wandb/cg/browser/ops';
import * as CG from '@wandb/cg/browser/graph';
import * as Types from '@wandb/cg/browser/model/types';
import {callFunction} from '@wandb/cg/browser/hl';

import * as Panel2 from './panel';
import * as KeyValTable from './KeyValTable';
import {PanelString, Spec as PanelStringSpec} from './PanelString';
import {PanelNumber, Spec as PanelNumberSpec} from './PanelNumber';
import {Spec as PanelDateSpec} from './PanelDate';
import PanelDate from './PanelDate/Component';
import * as ConfigPanel from './ConfigPanel';

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
  const inputVar = useMemo(
    () => CG.varNode(props.input.type, 'input'),
    [props.input.type]
  );

  const propertyTypes = Types.typedDictPropertyTypes(props.input.type);

  const propLimit = props.config?.propLimit ?? 100;

  const [keys, setKeys] = useState<string[]>([]);

  useEffect(() => {
    let newKeys = Object.keys(propertyTypes);
    if (newKeys.length > propLimit) {
      newKeys = newKeys.slice(0, propLimit);
    }

    if (!_.isEqual(newKeys, keys)) {
      setKeys(newKeys);
    }
  }, [propertyTypes, propLimit, setKeys]);

  const updateInput = useCallback(
    (key, newInput) => {
      if (newInput == null) {
        return props.updateInput?.(
          Op.opPick({
            obj: inputVar,
            key: Op.constString(key),
          }) as any
        );
      } else {
        const input = Op.opPick({
          obj: inputVar,
          key: Op.constString(key),
        });
        const innerFunction = callFunction((newInput as any).path, {
          input,
        });
        return props.updateInput?.(innerFunction as any);
      }
    },
    [inputVar, props.updateInput]
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
            {Types.isAssignableTo2(
              propertyTypes[k]!,
              PanelStringSpec.inputType
            ) ? (
              <PanelString
                input={
                  Op.opPick({
                    obj: props.input,
                    key: Op.constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : Types.isAssignableTo2(
                propertyTypes[k]!,
                PanelNumberSpec.inputType
              ) ? (
              <PanelNumber
                input={
                  Op.opPick({
                    obj: props.input,
                    key: Op.constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : Types.isAssignableTo2(
                propertyTypes[k]!,
                PanelDateSpec.inputType
              ) ? (
              <PanelDate
                input={
                  Op.opPick({
                    obj: props.input,
                    key: Op.constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
              />
            ) : Types.isAssignableTo2(propertyTypes[k]!, Spec.inputType) ? (
              <PanelObject
                input={
                  Op.opPick({
                    obj: props.input,
                    key: Op.constString(k),
                  }) as any
                }
                context={props.context}
                updateContext={props.updateContext}
                // Get rid of updateConfig
                updateConfig={() => {}}
                updateInput={newInput => updateInput(k, newInput)}
              />
            ) : (
              <div>{Types.toString(propertyTypes[k]!, true)}</div>
            )}
          </KeyValTable.Val>
        </KeyValTable.Row>
      )),
    [keys]
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
