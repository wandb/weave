import React, {useState} from 'react';
import {Tailwind} from '../../../../../Tailwind';
import * as DropdownMenu from '../../../../../DropdownMenu';
import {Button} from '../../../../../Button';
import {Icon} from '../../../../../Icon';

type ThreadsPageProps = {
  entity: string;
  project: string;
  threadId?: string;
};

export const ThreadsPage = ({entity, project, threadId}: ThreadsPageProps) => {
  // State for dropdown
  const [isThreadMenuOpen, setIsThreadMenuOpen] = useState(false);

  return (
    <Tailwind style={{height: '100%'}}>
      <div className="flex h-full w-full flex-col">
        {/* Main Header */}
        <div className="flex h-44 min-h-44 items-center justify-between border-b border-moon-250 px-16">
          <div className="flex items-center gap-8">
            <h1 className="text-lg font-semibold">Thread Explorer</h1>
            <DropdownMenu.Root open={isThreadMenuOpen} onOpenChange={setIsThreadMenuOpen}>
              <DropdownMenu.Trigger>
                <Button variant="secondary" icon="overflow-vertical">
                  Select Thread
                </Button>
              </DropdownMenu.Trigger>
              <DropdownMenu.Content>
                <DropdownMenu.Item>Thread 1</DropdownMenu.Item>
                <DropdownMenu.Item>Thread 2</DropdownMenu.Item>
              </DropdownMenu.Content>
            </DropdownMenu.Root>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Panel - 30% */}
          <div className="flex flex-[3] flex-col border-r border-moon-250">
            <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
              <h2 className="text-sm font-semibold">Left Panel</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-8">
              {/* Left panel content */}
            </div>
            <div className="h-24 border-t border-moon-250 px-8">
              {/* Left panel footer */}
            </div>
          </div>

          {/* Center Panel - 40% */}
          <div className="flex flex-[4] flex-col">
            <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
              <h2 className="text-sm font-semibold">Center Panel</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-8">
              {/* Center panel content */}
            </div>
            <div className="h-24 border-t border-moon-250 px-8">
              {/* Center panel footer */}
            </div>
          </div>

          {/* Right Panel - 30% */}
          <div className="flex flex-[3] flex-col border-l border-moon-250">
            <div className="flex h-full flex-col">
              {/* First section - no top border */}
              <div className="flex flex-1 flex-col">
                <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
                  <h2 className="text-sm font-semibold">Section 1</h2>
                </div>
                <div className="flex-1 overflow-y-auto p-8">
                  {/* Section 1 content */}
                </div>
              </div>
              {/* Second section - with top border */}
              <div className="flex flex-1 flex-col border-t border-moon-250">
                <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
                  <h2 className="text-sm font-semibold">Section 2</h2>
                </div>
                <div className="flex-1 overflow-y-auto p-8">
                  {/* Section 2 content */}
                </div>
              </div>
              {/* Third section - with top border */}
              <div className="flex flex-1 flex-col border-t border-moon-250">
                <div className="flex h-32 items-center justify-between border-b border-moon-250 px-8">
                  <h2 className="text-sm font-semibold">Section 3</h2>
                </div>
                <div className="flex-1 overflow-y-auto p-8">
                  {/* Section 3 content */}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Main Footer */}
        <div className="flex h-32 items-center border-t border-moon-250 px-16">
          <span className="text-sm text-moon-500">Status: Ready</span>
        </div>
      </div>
    </Tailwind>
  );
};
