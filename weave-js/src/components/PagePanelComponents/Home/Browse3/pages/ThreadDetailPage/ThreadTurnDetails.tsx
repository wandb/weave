import React, {FC} from 'react';

export interface ThreadTurnDetailsProps {
  selectedTurnId?: string;
  isLoading?: boolean;
}

/**
 * ThreadTurnDetails displays detailed information for a selected turn.
 *
 * Shows input/output data, performance metrics, and other turn-specific information.
 *
 * @param selectedTurnId - The ID of the turn to display details for
 * @param isLoading - Whether turn details are currently loading
 *
 * @example
 * <ThreadTurnDetails
 *   selectedTurnId="turn_1"
 *   isLoading={false}
 * />
 */
export const ThreadTurnDetails: FC<ThreadTurnDetailsProps> = ({
  selectedTurnId,
  isLoading,
}) => {
  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-16">
        <div className="text-gray-500">Loading turn details...</div>
      </div>
    );
  }

  if (!selectedTurnId) {
    return (
      <div className="h-full p-16">
        <div className="flex h-full items-center justify-center rounded-lg border bg-white p-24">
          <div className="text-gray-500 text-center">
            <h3 className="mb-4 text-lg font-medium">No Turn Selected</h3>
            <p>Select a turn from the list to view its details.</p>
          </div>
        </div>
      </div>
    );
  }

  return <div className="h-full p-16">TBD</div>;
};
