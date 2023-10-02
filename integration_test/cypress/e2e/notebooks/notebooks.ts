import {exec, checkAllPanelsRendered} from '../testlib';

interface Notebook {
  cells: Array<{
    id: string;
    cell_type: 'code' | 'markdown';
    execution_count: number;
    outputs: Array<{
      output_type: 'execute_result' | 'display_data' | 'error';
      data: {
        'text/html'?: string;
      };
    }>;
    source: string[];
  }>;
}

function parseNotebook(s: string): Notebook {
  return JSON.parse(s);
}

function forEachWeaveOutputCellInNotebook(
  notebookPath: string,
  cellTest: (cellId: string) => void
) {
  cy.readFile(notebookPath).then(notebookContents => {
    const notebook = parseNotebook(notebookContents);
    let executionCount = 0;
    for (let i = 0; i < notebook.cells.length; i++) {
      const cell = notebook.cells[i];
      if (cell.cell_type !== 'code') {
        continue;
      }
      if (cell.source[0]?.includes('# weave-test-skip')) {
        continue;
      }
      executionCount++;
      if (cell.execution_count !== executionCount) {
        throw new Error(
          `Execution count mismatch for cell ${i}. Notebooks must be cleared and then re-run with pytest -nbmake before running cypress tests.`
        );
      }
      for (const output of cell.outputs) {
        if (output.output_type === 'error') {
          throw new Error(`Encountered python error in cell ${i}`);
        }
        if (output.output_type !== 'display_data') {
          continue;
        }
        const html = output.data['text/html'];
        if (html == null) {
          // Not a cell that output html
          continue;
        }
        const el = document.createElement('html');
        el.innerHTML = html;
        const iframe = el.getElementsByTagName('iframe')[0];
        const src = iframe.src;
        if (!src.includes('weave_jupyter')) {
          throw new Error(
            'Encountered an iframe output cell that is not a weave output'
          );
        }
        const url = new URL(src);

        // TODO: This switches depending on if in devmode
        cy.visit('/__frontend/weave_frontend' + url.search, {
          onBeforeLoad(win) {
            // Inject the monkey-patching script into the app running in the test
            const OriginalResizeObserver = win.ResizeObserver;
            win.ResizeObserver = class extends OriginalResizeObserver {
              constructor(callback) {
                super((entries, observer) => {
                  console.log('ResizeObserver Callback Triggered', { entries, observer });
                  callback(entries, observer);
                });
                console.log('A new ResizeObserver was created', this);
              }
              observe(target) {
                console.log('A new target is being observed by a ResizeObserver', target);
                super.observe(target);
              }
            };
          }
        });
        
        // cy.visit('http://localhost:3000/' + url.search);

        cellTest(cell.id);
      }
    }
  });
}

function executeNotebook(notebookPath: string) {
  exec(
    'pytest --nbmake --nbmake-timeout=150000 --overwrite "' +
      notebookPath +
      '"',
    150000
  );
}

export function checkWeaveNotebookOutputs(notebookPath: string) {
  cy.readFile(notebookPath).then(notebookContents => {
    const notebook = parseNotebook(notebookContents);
    if (notebook.cells[0].source[0]?.includes('# weave-test-skip-all')) {
      cy.log(
        'Skipping notebook due to weave-test-skip-all directive ' + notebookPath
      );
      return;
    }
    executeNotebook(notebookPath);
    forEachWeaveOutputCellInNotebook(notebookPath, cellId => {
      // assert that there is at least 1 element with an attribute 'data-test-weave-id'
      checkAllPanelsRendered();
      cy.wait(1000);
      checkAllPanelsRendered();
    });
  });
}
