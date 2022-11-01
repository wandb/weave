interface Notebook {
  cells: Array<{
    cell_type: 'code' | 'markdown';
    execution_count: number;
    outputs: Array<{
      output_type: 'execute_result' | 'display_data' | 'error';
      data: {
        'text/html'?: string;
      };
    }>;
  }>;
}

function parseNotebook(s: string): Notebook {
  return JSON.parse(s);
}

function forEachCellInNotebook(notebookPath: string, cellTest: () => void) {
  cy.readFile(notebookPath).then(notebookContents => {
    const notebook = parseNotebook(notebookContents);
    let executionCount = 0;
    for (let i = 0; i < notebook.cells.length; i++) {
      const cell = notebook.cells[i];
      if (cell.cell_type !== 'code') {
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
          break;
        }
        const html = output.data['text/html'];
        if (html == null) {
          // Not a cell that output html
          break;
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
        cy.visit('http://localhost:9994/__frontend/weave' + url.search);
        // cy.visit('http://localhost:3000/' + url.search);

        cellTest();
      }
    }
  });
}

function checkNotebookOutputsExist() {
  const panels = cy
    .get('[data-test-weave-id]', {timeout: 10000})
    .should('have.length.greaterThan', 0);
  panels.each((panel, index) => {
    // assert that the element has a non-empty attribute 'data-test-weave-id'
    const panelId = panel.attr('data-test-weave-id');
    if (panelId == 'PanelPlotly') {
      cy.wrap(panel).find('.plotly').should('exist');
    } else if (panelId == 'table') {
      cy.wrap(panel).find('.BaseTable').should('exist');
    } else {
      throw new Error(
        `Unknown weave panel type (${panelId}). You should add assertions for it.`
      );
    }
  });
}

export function checkWeaveNotebookOutputs(notebookPath: string) {
  forEachCellInNotebook(notebookPath, () => {
    // assert that there is at least 1 element with an attribute 'data-test-weave-id'
    checkNotebookOutputsExist();
    cy.wait(5000);
    checkNotebookOutputsExist();
  });
}
