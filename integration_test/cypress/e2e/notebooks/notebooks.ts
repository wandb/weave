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
        cy.visit('/__frontend/weave_frontend' + url.search);

        // Cypress is erroring on ResizeObserver loop limit exceeded, but
        // we are not seeing anything like this locally. I think it might
        // have to do with cypress itself. Similar issues have been noted
        // here: https://github.com/cypress-io/cypress/issues/8418, with similar
        // patches resolving the issue. I'm not sure if this is the best way
        // to handle this, but it seems to work.
        cy.on('uncaught:exception', err => {

          if (
            err.name?.includes('ResizeObserver') ||
            err.message?.includes('ResizeObserver')
          ) {
            return false;

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
    'pytest --nbmake --nbmake-timeout=3000 --overwrite "' + notebookPath + '"',
    160000
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
