import {Button} from '@wandb/weave/components/Button';
import {Checkbox} from '@wandb/weave/components/Checkbox';
import {TextField} from '@wandb/weave/components/Form/TextField';
import React, {useEffect, useRef, useState} from 'react';

interface CostsFiltersProps {
  showOnlyLatest: boolean;
  onShowOnlyLatestChange: (checked: boolean) => void;
  showCloseToZero: boolean;
  onShowCloseToZeroChange: (checked: boolean) => void;
  showProjectCostsFirst: boolean;
  onShowProjectCostsFirstChange: (checked: boolean) => void;
  searchText: string;
  onSearchChange: (value: string) => void;
  onAddCostClick: () => void;
  selectedCosts: Set<string>;
  onBulkDelete: (costIds: string[]) => void;
}

export const CostsFilters: React.FC<CostsFiltersProps> = ({
  showOnlyLatest,
  onShowOnlyLatestChange,
  showCloseToZero,
  onShowCloseToZeroChange,
  showProjectCostsFirst,
  onShowProjectCostsFirstChange,
  searchText,
  onSearchChange,
  onAddCostClick,
  selectedCosts,
  onBulkDelete,
}) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleBulkDeleteClick = () => {
    const selectedIds = Array.from(selectedCosts);
    onBulkDelete(selectedIds);
  };

  return (
    <div className="my-8 flex w-full justify-between gap-4">
      <div className="flex items-center gap-8">
        <div className="w-[350px]">
          <TextField
            placeholder="Search by model, provider, or level..."
            value={searchText}
            onChange={onSearchChange}
            icon="search"
          />
        </div>
      </div>
      <div className="flex items-center gap-8">
        {selectedCosts.size > 0 && (
          <Button
            variant="destructive"
            size="medium"
            icon="delete"
            onClick={handleBulkDeleteClick}
            tooltip={`Delete ${selectedCosts.size} selected cost${
              selectedCosts.size === 1 ? '' : 's'
            }`}>
            {`Delete (${selectedCosts.size})`}
          </Button>
        )}

        <Button
          variant="primary"
          size="medium"
          icon="add-new"
          onClick={onAddCostClick}>
          Add Cost
        </Button>

        {/* Dropdown menu for filter options */}

        <div className="relative" ref={dropdownRef}>
          <Button
            variant="ghost"
            size="medium"
            icon="overflow-horizontal"
            onClick={() => setShowDropdown(!showDropdown)}
            tooltip="Filter options"
          />

          {showDropdown && (
            <div className="absolute right-0 top-full z-10 mt-8 w-80 w-[300px] rounded-lg border border-moon-200 bg-white p-16 shadow-lg">
              <div className="flex flex-col gap-4">
                <div className="flex items-center gap-8">
                  <Checkbox
                    checked={showProjectCostsFirst}
                    onCheckedChange={onShowProjectCostsFirstChange}
                  />
                  <label className="text-sm">
                    Show project level costs at the top
                  </label>
                </div>

                <div className="flex items-center gap-8">
                  <Checkbox
                    checked={showOnlyLatest}
                    onCheckedChange={onShowOnlyLatestChange}
                  />
                  <label className="text-sm">Show only most recent costs</label>
                </div>

                <div className="flex items-center gap-8">
                  <Checkbox
                    checked={showCloseToZero}
                    onCheckedChange={onShowCloseToZeroChange}
                  />
                  <label className="text-sm">Show costs close to zero</label>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
