import {MOON_600, MOON_800} from '@wandb/weave/common/css/color.styles';
import {CodeEditor} from '@wandb/weave/components/CodeEditor';
import {StyledDataGrid} from '@wandb/weave/components/PagePanelComponents/Home/Browse3/StyledDataGrid';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import {ToggleButtonGroup} from '@wandb/weave/components/ToggleButtonGroup';
import React, {FC, useMemo, useState} from 'react';

import {CellValueString} from '../../../Browse2/CellValueString';

const flattenObject = (
  obj: any,
  prefix = ''
): Array<{path: string; value: any}> => {
  const result: Array<{path: string; value: any}> = [];
  if (typeof obj !== 'object' || obj === null) {
    result.push({path: prefix, value: obj});
    return result;
  }
  if (Array.isArray(obj)) {
    obj.forEach((item, idx) => {
      const path = prefix ? `${prefix}.${idx}` : String(idx);
      result.push(...flattenObject(item, path));
    });
  } else {
    Object.entries(obj).forEach(([key, val]) => {
      const path = prefix ? `${prefix}.${key}` : key;
      result.push(...flattenObject(val, path));
    });
  }
  return result;
};

/**
 * Tab switcher for structured outputs: path-value table and Code view
 *
 * Props:
 *   value: string (JSON string) This should always be a valid JSON string
 *
 * Example:
 *   <StructuredOutputsMessagePart value={jsonString} />
 */
export const StructuredOutputsMessagePart: FC<{
  value: string;
}> = ({value}) => {
  const [tab, setTab] = useState('table');

  let parsed: any = null;
  let error: string | null = null;
  try {
    parsed = JSON.parse(value);
  } catch (e: any) {
    console.error('Invalid JSON string', e);
    error = e.message;
  }

  // Prepare path-value pairs for display
  const pathValueRows = useMemo(() => {
    if (!parsed || typeof parsed !== 'object') return [];
    return flattenObject(parsed).map((row, idx) => ({id: idx, ...row}));
  }, [parsed]);

  // This should never happen, but just in case
  if (error) {
    return <span className="text-red-500">{error}</span>;
  }

  const columns = [
    {
      field: 'path',
      headerName: '',
      flex: 1,
      minWidth: 80,
      renderCell: (params: any) => (
        <CellValueString
          value={params.value}
          style={{
            fontSize: 14,
            color: MOON_600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        />
      ),
    },
    {
      field: 'value',
      headerName: '',
      flex: 2,
      minWidth: 200,
      renderCell: (params: any) => (
        <CellValueString
          value={String(params.value)}
          style={{
            fontSize: 14,
            color: MOON_800,
          }}
        />
      ),
    },
  ];

  return (
    <Tailwind>
      <div className="mb-2">
        <ToggleButtonGroup
          options={[
            {icon: 'table', iconOnly: true, value: 'table'},
            {icon: 'code-alt', iconOnly: true, value: 'json'},
          ]}
          value={tab}
          size="small"
          onValueChange={setTab}
        />
      </div>
      {tab === 'table' ? (
        <div className="w-full overflow-hidden rounded-md border border-moon-200 bg-white">
          <StyledDataGrid
            autoHeight
            rows={pathValueRows}
            columns={columns}
            hideFooter
            disableRowSelectionOnClick
            rowHeight={38}
            sx={{
              '& .MuiDataGrid-columnHeaders': {display: 'none'},
              border: 'none',
            }}
          />
        </div>
      ) : (
        <CodeEditor
          language="json"
          value={JSON.stringify(parsed, null, 2)}
          readOnly
        />
      )}
    </Tailwind>
  );
};
