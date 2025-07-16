import {Button} from '@wandb/weave/components/Button';
import {TextField} from '@wandb/weave/components/Form/TextField';
import {Tailwind} from '@wandb/weave/components/Tailwind';
import React, {useCallback, useEffect, useState} from 'react';

import {ResizableDrawer} from '../common/ResizableDrawer';
import {CostQueryOutput} from '../wfReactInterface/traceServerClientTypes';

export interface AddCostForm {
  llm_id: string;
  provider_id: string;
  prompt_token_cost: string;
  completion_token_cost: string;
  effective_date: string;
}

interface AddCostDrawerProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (form: AddCostForm) => Promise<void>;
  editingCost?: CostQueryOutput | null;
}

export const AddCostDrawer: React.FC<AddCostDrawerProps> = ({
  open,
  onClose,
  onSubmit,
  editingCost,
}) => {
  const [form, setForm] = useState<AddCostForm>({
    llm_id: '',
    provider_id: '',
    prompt_token_cost: '',
    completion_token_cost: '',
    effective_date: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isEditing = !!editingCost;

  const resetForm = useCallback(() => {
    setForm({
      llm_id: '',
      provider_id: '',
      prompt_token_cost: '',
      completion_token_cost: '',
      effective_date: '',
    });
  }, []);

  // Populate form when editing
  useEffect(() => {
    if (editingCost) {
      setForm({
        llm_id: editingCost.llm_id || '',
        provider_id: editingCost.provider_id || '',
        prompt_token_cost: editingCost.prompt_token_cost
          ? Number(editingCost.prompt_token_cost).toFixed(8)
          : '',
        completion_token_cost: editingCost.completion_token_cost
          ? Number(editingCost.completion_token_cost).toFixed(8)
          : '',
        effective_date: editingCost.effective_date || '',
      });
    } else {
      resetForm();
    }
  }, [editingCost, open, resetForm]);

  const handleClose = useCallback(() => {
    resetForm();
    onClose();
  }, [onClose, resetForm]);

  const handleSubmit = useCallback(async () => {
    if (
      !form.llm_id ||
      !form.provider_id ||
      !form.prompt_token_cost ||
      !form.completion_token_cost
    ) {
      alert('Please fill in all required fields');
      return;
    }

    setIsSubmitting(true);
    try {
      await onSubmit(form);
      resetForm();
      onClose();
    } catch (error) {
      console.error('Error creating cost:', error);
      alert('Failed to create cost. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }, [form, onSubmit, resetForm, onClose]);

  // Memoized form field handlers to prevent unnecessary re-renders
  const handleLlmIdChange = useCallback((value: string) => {
    setForm(prev => ({...prev, llm_id: value}));
  }, []);

  const handleProviderIdChange = useCallback((value: string) => {
    setForm(prev => ({...prev, provider_id: value}));
  }, []);

  const handlePromptTokenCostChange = useCallback((value: string) => {
    setForm(prev => ({...prev, prompt_token_cost: value}));
  }, []);

  const handleCompletionTokenCostChange = useCallback((value: string) => {
    setForm(prev => ({...prev, completion_token_cost: value}));
  }, []);

  const handleEffectiveDateChange = useCallback((value: string) => {
    setForm(prev => ({...prev, effective_date: value}));
  }, []);

  return (
    <ResizableDrawer
      open={open}
      onClose={handleClose}
      defaultWidth={480}
      marginTop={60}
      headerContent={
        <Tailwind>
          <div className="flex h-64 items-center justify-between border-b border-moon-200 px-16 py-8">
            <span className="text-2xl font-semibold">
              {isEditing ? 'Edit Cost' : 'Add New Cost'}
            </span>
            <Button icon="close" variant="ghost" onClick={handleClose} />
          </div>
        </Tailwind>
      }>
      <Tailwind style={{height: '100%'}}>
        <div className="flex h-full flex-col justify-between overflow-hidden">
          {/* Content */}
          <div className="flex flex-1 flex-col gap-8 overflow-hidden px-16 py-16">
            {isEditing && (
              <div className="bg-blue-50 text-blue-800 mb-4 rounded-lg p-4 text-sm">
                <strong>Note:</strong> Editing this cost will create a new
                project-level cost entry.
              </div>
            )}
            <div className="flex flex-col gap-6">
              <div>
                <label className="mb-1 block text-base font-semibold">
                  Model ID *
                </label>
                <TextField
                  placeholder="gpt-4o-mini-2024-07-18"
                  value={form.llm_id}
                  onChange={handleLlmIdChange}
                />
              </div>

              <div>
                <label className="mb-1 block text-base font-semibold">
                  Provider ID *
                </label>
                <TextField
                  placeholder="openai"
                  value={form.provider_id}
                  onChange={handleProviderIdChange}
                />
              </div>

              <div>
                <label className="mb-1 block text-base font-semibold">
                  Prompt Token Cost *
                </label>
                <TextField
                  placeholder="e.g., 0.00000150"
                  value={form.prompt_token_cost}
                  onChange={handlePromptTokenCostChange}
                  type="number"
                  step={0.00000001}
                />
              </div>

              <div>
                <label className="mb-1 block text-base font-semibold">
                  Completion Token Cost *
                </label>
                <TextField
                  placeholder="0.00000600"
                  value={form.completion_token_cost}
                  onChange={handleCompletionTokenCostChange}
                  type="number"
                  step={0.00000001}
                />
              </div>

              <div>
                <label className="mb-1 block text-base font-semibold">
                  Effective Date
                </label>
                <TextField
                  placeholder="YYYY-MM-DD or leave empty for current date"
                  value={form.effective_date}
                  onChange={handleEffectiveDateChange}
                  type="date"
                />
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex gap-2 border-t border-moon-200 px-0 py-16">
            <div className="flex w-full gap-8 px-16">
              <Button
                onClick={handleClose}
                variant="secondary"
                className="flex-1"
                twWrapperStyles={{flex: 1}}
                disabled={isSubmitting}>
                Cancel
              </Button>
              <Button
                onClick={handleSubmit}
                variant="primary"
                className="flex-1"
                twWrapperStyles={{flex: 1}}
                disabled={isSubmitting}>
                {isSubmitting
                  ? isEditing
                    ? 'Saving...'
                    : 'Adding...'
                  : isEditing
                  ? 'Save Cost'
                  : 'Add Cost'}
              </Button>
            </div>
          </div>
        </div>
      </Tailwind>
    </ResizableDrawer>
  );
};
