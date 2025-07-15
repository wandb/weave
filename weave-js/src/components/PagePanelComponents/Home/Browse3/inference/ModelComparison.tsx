import classNames from 'classnames';
import copyToClipboard from 'copy-to-clipboard';
import React, {useCallback, useEffect, useRef, useState} from 'react';
import {useHistory} from 'react-router-dom';
import {toast} from 'react-toastify';

import {TargetBlank} from '../../../../../common/util/links';
import {Alert} from '../../../../Alert';
import {Button} from '../../../../Button';
import {Pill} from '../../../../Tag';
import {Tooltip} from '../../../../Tooltip';
import {NotApplicable} from '../NotApplicable';
import {Link} from '../pages/common/Links';
import {EVALUATIONS, PropertyId, TIME_METRICS} from './comparison';
import {Property} from './comparison';
import {DiffPill} from './DiffPill';
import {Modalities} from './Modalities';
import {ModelComparisonDropdown} from './ModelComparisonDropdown';
import {ModelComparisonRowHeader} from './ModelComparisonRowHeader';
import {getModelsByIds, MODEL_INFO} from './modelInfo';
import {SelectModelAdd} from './SelectModelAdd';
import {Model} from './types';
import {
  getContextWindowString,
  getLaunchDateString,
  getModelLabel,
  getModelLogo,
  getModelSourceName,
  getOnePriceString,
  getShortNumberString,
  urlInference,
} from './util';

type ModelColumnTitleProps = {
  index: number;
  numModels: number;
  model: Model;
  onMakeBaseline: (modelId: string) => void;
  onToggleModel: (modelId: string) => void;
};

const ModelColumnTitle = ({
  index,
  numModels,
  model,
  onMakeBaseline,
  onToggleModel,
}: ModelColumnTitleProps) => {
  const label = getModelLabel(model);
  const urlDetails = urlInference(model.provider, model.id);
  const logo = getModelLogo(model);
  const logoImg = logo ? (
    <Tooltip
      trigger={<img width={24} height={24} src={logo} alt="" />}
      content={getModelSourceName(model)}
    />
  ) : null;

  const onMakeModelBaseline = useCallback(() => {
    onMakeBaseline(model.id);
  }, [model.id, onMakeBaseline]);

  const onRemoveFromComparison = useCallback(() => {
    onToggleModel(model.id);
  }, [model.id, onToggleModel]);

  return (
    <div className="border-b-1 whitespace-nowrap border-solid border-moon-500 pb-2 text-center text-lg font-semibold">
      <div className="flex items-center justify-center gap-8">
        <div className="flex items-center gap-8 text-lg font-semibold text-teal-600">
          {logoImg}
          <Link to={urlDetails}>{label}</Link>
          {index === 0 && (
            <Pill color="teal" label="Baseline" className="ml-8" />
          )}
        </div>
        <ModelComparisonDropdown
          index={index}
          numModels={numModels}
          onMakeBaseline={onMakeModelBaseline}
          onRemoveFromComparison={onRemoveFromComparison}
        />
      </div>
    </div>
  );
};

function getBackgroundColor(pct: number): string {
  // Example: green gradient using HSL from light to dark
  const lightness = 100 - pct * 0.5; // from 100% to 50%
  return `hsl(120, 40%, ${lightness}%)`; // hue=120 for green, reduced saturation for less intensity
}

type NumberFormatter = (value: number) => string;

const shortNumberFormatter: NumberFormatter = (value: number) =>
  getShortNumberString(value, 0);

const priceNumberFormatter: NumberFormatter = (value: number) =>
  getOnePriceString(value);

type Accessor = string | ((model: Model) => number);

const accessModelValue = (model: Model, accessor: Accessor) => {
  if (typeof accessor === 'string') {
    return model[accessor];
  }
  return accessor(model);
};

const diffRenderer = (
  accessor: Accessor,
  index: number,
  models: Model[],
  numberFormatter: NumberFormatter,
  lowerIsBetter?: boolean
) => {
  const value = accessModelValue(models[index], accessor);
  const baselineValue =
    index !== 0 ? accessModelValue(models[0], accessor) : null;

  const valuesArray = models.map(m => accessModelValue(m, accessor));
  const operation = lowerIsBetter ? Math.min : Math.max;
  const bestValue = operation(...valuesArray.filter(v => v != null));
  const isBest = value === bestValue;
  return (
    <td className="py-2 transition-colors duration-200 ">
      {value ? (
        <div className="flex items-center justify-center gap-8">
          <span
            title={value.toLocaleString()}
            className={classNames({'font-bold': isBest})}>
            {numberFormatter(value)}
          </span>
          {baselineValue !== null && (
            <DiffPill
              value={value}
              compareValue={baselineValue}
              valueFormatter={numberFormatter}
              lowerIsBetter={lowerIsBetter}
            />
          )}
        </div>
      ) : (
        <NotApplicable />
      )}
    </td>
  );
};

type ModelComparisonProps = {
  modelIds: string[];
  onMakeBaseline: (modelId: string) => void;
  onToggleModel: (modelId: string) => void;
  propertyIds: string[];
  onToggleProperty: (propertyId: string) => void;
};

export const ModelComparison = ({
  modelIds,
  onMakeBaseline,
  onToggleModel,
  propertyIds,
  onToggleProperty,
}: ModelComparisonProps) => {
  if (modelIds.length === 0) {
    return (
      <div className="m-16">
        <div className="mb-8 text-xl font-semibold text-moon-800">
          Compare models
        </div>
        <Alert severity="info">Please select models to compare</Alert>
        <div className="mt-16">
          <SelectModelAdd
            modelInfo={MODEL_INFO}
            value=""
            onSelectModelAdd={(id: string) => {
              onToggleModel(id);
            }}
            alreadySelected={modelIds}
          />
        </div>
      </div>
    );
  }
  const models = getModelsByIds(modelIds);
  return (
    <div className="m-16">
      <ModelComparisonInner
        modelIds={modelIds}
        models={models}
        onMakeBaseline={onMakeBaseline}
        onToggleModel={onToggleModel}
        propertyIds={propertyIds}
        onToggleProperty={onToggleProperty}
      />
    </div>
  );
};

type ModelComparisonInnerProps = {
  modelIds: string[]; // Could get this from models but we already have it
  models: Model[];
  onMakeBaseline: (modelId: string) => void;
  onToggleModel: (modelId: string) => void;
  propertyIds: string[];
  onToggleProperty: (propertyId: string) => void;
};

type RowDefintion = Omit<Property, 'id'> & {
  render: (model: Model, index: number, models: Model[]) => React.JSX.Element;
};

export const ModelComparisonInner = ({
  modelIds,
  models,
  onMakeBaseline,
  onToggleModel,
  propertyIds,
  onToggleProperty,
}: ModelComparisonInnerProps) => {
  const history = useHistory();
  // const baselineEnabled = queryGetBoolean(history, 'baseline', false);
  // const selected = queryGetString(history, 'sel');

  const [isAddingModel, setIsAddingModel] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  // Scroll the close button into view when adding model
  useEffect(() => {
    if (isAddingModel && closeButtonRef.current) {
      // Use setTimeout to ensure the DOM has updated
      setTimeout(() => {
        closeButtonRef.current?.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
          inline: 'nearest',
        });
      }, 100);
    }
  }, [isAddingModel]);

  // const cartItems = models.map(m => {
  //   return {
  //     key: 'model',
  //     value: m.id,
  //     label: m.label ?? m.id,
  //   };
  // });

  // TODO: Add an id, then make row
  const rowDefinitions: Record<PropertyId, RowDefintion> = {
    descriptionShort: {
      label: 'Description',
      isSelectable: false,
      render: (model: Model, index: number) => (
        <td
          key={`descriptionShort-${index}`}
          className="py-2 text-center align-top transition-colors duration-200 ">
          {model.descriptionShort || <NotApplicable />}
        </td>
      ),
    },
    source: {
      label: 'Source',
      isSelectable: true,
      render: (model: Model, index: number) => {
        const sourceName = getModelSourceName(model);
        return (
          <td
            key={`source-${index}`}
            className="py-2 text-center align-top transition-colors duration-200 ">
            <div className="flex items-center justify-center gap-4">
              {sourceName}
            </div>
          </td>
        );
      },
    },
    modalities: {
      label: 'Modalities',
      isSelectable: false,
      render: (model: Model, index: number) => (
        <td
          key={`modalities-${index}`}
          className="py-2 transition-colors duration-200 ">
          {model.modalities && (
            <div className="flex justify-center">
              <Modalities modalities={model.modalities} />
            </div>
          )}
        </td>
      ),
    },
    idHuggingFace: {
      label: 'Hugging Face',
      isSelectable: false,
      render: (model: Model, index: number) => (
        <td
          key={`idHuggingFace-${index}`}
          className="py-2 text-center transition-colors duration-200 ">
          {model.idHuggingFace ? (
            <div className="flex items-center justify-center whitespace-nowrap">
              <TargetBlank href={model.urlHuggingFace}>
                {model.idHuggingFace}
              </TargetBlank>
              <Button
                className="ml-4"
                size="small"
                icon="copy"
                variant="ghost"
                onClick={() => {
                  copyToClipboard(model.idHuggingFace ?? '');
                  toast('Copied to clipboard');
                }}
                tooltip="Copy model ID to clipboard"
              />
            </div>
          ) : (
            <NotApplicable />
          )}
        </td>
      ),
    },
    likesHuggingFace: {
      label: 'Hugging Face Likes',
      isSelectable: true,
      render: (model: Model, index: number, models: Model[]) =>
        diffRenderer('likesHuggingFace', index, models, shortNumberFormatter),
    },
    downloadsHuggingFace: {
      label: 'Hugging Face Downloads',
      isSelectable: true,
      render: (model: Model, index: number, models: Model[]) =>
        diffRenderer(
          'downloadsHuggingFace',
          index,
          models,
          shortNumberFormatter
        ),
    },
    priceCentsPerBillionTokensInput: {
      label: 'Input Price',
      labelSecondary: 'per 1M tokens',
      isSelectable: true,
      render: (model: Model, index: number, models: Model[]) =>
        diffRenderer(
          'priceCentsPerBillionTokensInput',
          index,
          models,
          priceNumberFormatter,
          true // lower is better
        ),
    },
    priceCentsPerBillionTokensOutput: {
      label: 'Output Price',
      labelSecondary: 'per 1M tokens',
      isSelectable: true,
      render: (model: Model, index: number, models: Model[]) =>
        diffRenderer(
          'priceCentsPerBillionTokensOutput',
          index,
          models,
          priceNumberFormatter,
          true // lower is better
        ),
    },
    contextWindow: {
      label: 'Context Window',
      isSelectable: true,
      render: (model: Model, index: number) => (
        <td
          key={`contextWindow-${index}`}
          className="py-2 text-center transition-colors duration-200 ">
          {getContextWindowString(model) ? (
            `${getContextWindowString(model)} tokens`
          ) : (
            <NotApplicable />
          )}
        </td>
      ),
    },
    parameterCountTotal: {
      label: 'Total Parameter Count',
      isSelectable: true,
      render: (model: Model, index: number) => (
        <td
          key={`parameterCountTotal-${index}`}
          className="py-2 text-center transition-colors duration-200 ">
          {model.parameterCountTotal ? (
            getShortNumberString(model.parameterCountTotal)
          ) : (
            <NotApplicable />
          )}
        </td>
      ),
    },
    parameterCountActive: {
      label: 'Active Parameter Count',
      isSelectable: true,
      render: (model: Model, index: number) => (
        <td
          key={`parameterCountActive-${index}`}
          className="py-2 text-center transition-colors duration-200 ">
          {model.parameterCountActive ? (
            getShortNumberString(model.parameterCountActive)
          ) : (
            <NotApplicable />
          )}
        </td>
      ),
    },
    license: {
      label: 'License',
      isSelectable: true,
      render: (model: Model, index: number) => (
        <td
          key={`license-${index}`}
          className="py-2 text-center transition-colors duration-200 ">
          {model.license ?? <NotApplicable />}
        </td>
      ),
    },
    launchDate: {
      label: 'Launch Date',
      isSelectable: true,
      render: (model: Model, index: number) => (
        <td
          key={`launchDate-${index}`}
          className="py-2 text-center transition-colors duration-200">
          {getLaunchDateString(model) || <NotApplicable />}
        </td>
      ),
    },
  };

  for (const evaluation of EVALUATIONS) {
    rowDefinitions[evaluation.id] = {
      label: evaluation.label,
      labelSecondary: evaluation.labelSecondary,
      tooltip: evaluation.tooltip,
      isSelectable: true,
      render: (model: Model, index: number, models: Model[]) => {
        const value = model.artificialAnalysis?.evaluations?.[evaluation.id];
        const valuesArray = models.map(
          m => m.artificialAnalysis?.evaluations?.[evaluation.id]
        );
        const maxValue = Math.max(...valuesArray.filter(v => v != null));
        const isBest = value === maxValue;
        const normalizedValue =
          value != null
            ? evaluation.type === 'percentage'
              ? value * 100
              : value
            : 0;
        let displayValue: string | React.JSX.Element = <NotApplicable />;
        if (value != null) {
          if (evaluation.type === 'percentage') {
            displayValue = `${(value * 100).toFixed(2)}%`;
          } else {
            displayValue = value.toFixed(2);
          }
        }
        const bgColor = getBackgroundColor(normalizedValue);
        return (
          <td
            style={{backgroundColor: bgColor}}
            className={classNames(
              'py-2 text-center transition-colors duration-200',
              {'font-bold': isBest}
            )}>
            {displayValue}
          </td>
        );
      },
    };
  }

  for (const timeMetric of TIME_METRICS) {
    rowDefinitions[timeMetric.id] = {
      label: timeMetric.label,
      labelSecondary: timeMetric.labelSecondary,
      isSelectable: true,
      render: (model: Model, index: number, models: Model[]) =>
        diffRenderer(
          (model: Model) => model.artificialAnalysis?.[timeMetric.id],
          index,
          models,
          (value: number) => value.toFixed(2),
          timeMetric.lowerIsBetter
        ),
      // const value = model.artificialAnalysis?.[timeMetric.id];
      // const valuesArray = models.map(
      //   m => m.artificialAnalysis?.[timeMetric.id]
      // );
      // const operation = timeMetric.lowerIsBetter ? Math.min : Math.max;
      // const bestValue = operation(...valuesArray.filter(v => v != null));
      // const isBest = value === bestValue;
      // let displayValue: string | React.JSX.Element = <NotApplicable />;

      // if (value != null) {
      //   displayValue = value.toFixed(2);
      // }
      // return (
      //   <td
      //     className={classNames(
      //       'py-2 text-center transition-colors duration-200',
      //       {'font-bold': isBest}
      //     )}>
      //     {displayValue}
      //   </td>
      // );
    };
  }

  // const rowIds = [
  //   'descriptionShort',
  //   'idHuggingFace',
  //   'priceCentsPerBillionTokensInput',
  //   'priceCentsPerBillionTokensOutput',
  //   'contextWindow',
  // ];
  const rowIds = Object.keys(rowDefinitions);

  const rows = rowIds.map(id => ({id, ...rowDefinitions[id]}));

  return (
    <div>
      <div className="mb-8 flex items-center justify-between">
        <div className="text-xl font-semibold text-moon-800">
          Compare models
        </div>
        <div className="flex gap-8">
          <Button
            size="large"
            variant="secondary"
            icon="add-new"
            onClick={() => {
              setIsAddingModel(true);
            }}
            disabled={isAddingModel}>
            Add model
          </Button>
          <Button
            size="large"
            icon="chart-scatterplot"
            tooltip="Select rows to visualize properties"
            onClick={() => {
              history.push({
                pathname: '/inference-visualize',
                search: window.location.search,
              });
            }}>
            Visualize
          </Button>
        </div>
      </div>

      {/* <div className="my-8">
        <ShoppingCart
          items={cartItems}
          baselineEnabled={baselineEnabled}
          selected={selected}
        />
      </div> */}

      <div className="bg-gray-100 group rounded-lg p-4">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="space-x-1">
                <th className="sticky left-0 w-64 border-b-2 border-solid border-moon-150 bg-moon-100 p-2 text-left"></th>
                {models.map((model, index) => (
                  <th
                    key={`header-${index}`}
                    className="border-b-2 border-solid border-moon-150 p-2 text-center">
                    <ModelColumnTitle
                      index={index}
                      numModels={models.length}
                      model={model}
                      onMakeBaseline={onMakeBaseline}
                      onToggleModel={onToggleModel}
                    />
                  </th>
                ))}
                {isAddingModel && (
                  <th>
                    <div className="flex items-center gap-4">
                      <div className="min-w-[300px]">
                        <SelectModelAdd
                          modelInfo={MODEL_INFO}
                          value=""
                          alreadySelected={modelIds}
                          onSelectModelAdd={(id: string) => {
                            console.log({id});
                            const currentParams = new URLSearchParams(
                              window.location.search
                            );
                            currentParams.append('model', id);
                            history.push({search: currentParams.toString()});
                            setIsAddingModel(false);
                          }}
                        />
                      </div>
                      <div>
                        <Button
                          ref={closeButtonRef}
                          icon="close"
                          variant="ghost"
                          size="medium"
                          onClick={() => setIsAddingModel(false)}
                        />
                      </div>
                    </div>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const isSelected = propertyIds.includes(row.id);
                return (
                  <tr
                    key={row.id}
                    className={classNames(
                      'space-x-1 bg-moon-50 hover:bg-moon-100',
                      {
                        'bg-teal-300/[0.24] hover:bg-teal-400/[0.24]':
                          isSelected,
                      },
                      {
                        'cursor-pointer': row.isSelectable,
                      }
                    )}
                    onClick={
                      row.isSelectable
                        ? () => onToggleProperty(row.id)
                        : undefined
                    }>
                    <td
                      className={classNames(
                        // opaque bg required so other <td>s don't show through on horizontal scroll
                        'sticky left-0 whitespace-nowrap border-r border-moon-200 bg-moon-100 p-4 font-semibold transition-colors duration-200',
                        {
                          'bg-[#DBF0F2FF]': isSelected,
                        }
                      )}>
                      <ModelComparisonRowHeader
                        label={row.label}
                        labelSecondary={row.labelSecondary}
                        tooltip={row.tooltip}
                      />
                    </td>
                    {models.map((model, index) =>
                      row.render(model, index, models)
                    )}
                    {isAddingModel && <td />}
                  </tr>
                );
              })}
              {/*
              <tr className="space-x-1  hover:bg-moon-150">
                <td className="sticky left-0 whitespace-nowrap border-r border-moon-200 bg-moon-100 px-2 py-2 font-medium transition-colors duration-200 ">
                  Status
                </td>
                {models.map((model, index) => (
                  <td
                    key={`status-${index}`}
                    className="py-2 text-center transition-colors duration-200 ">
                    {model.status || <NotApplicable />}
                  </td>
                ))}
              </tr> */}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
