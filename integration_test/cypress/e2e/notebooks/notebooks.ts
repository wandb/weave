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
        cy.visit('/__frontend/weave' + url.search);
        // cy.visit('http://localhost:3000/' + url.search);

        cellTest(cell.id);
      }
    }
  });
}

function checkNotebookOutputsExist() {
  const panels = cy
    .get('[data-test-weave-id]', {timeout: 30000})
    .should('have.length.greaterThan', 0);
  panels.each((panel, index) => {
    // assert that the element has a non-empty attribute 'data-test-weave-id'
    const panelId = panel.attr('data-test-weave-id');
    if (panelId == 'PanelPlotly') {
      cy.wrap(panel).find('.plotly', {timeout: 30000}).should('exist');
    } else if (panelId == 'table') {
      cy.wrap(panel).find('.BaseTable').should('exist');
    } else if (panelId == 'html-file') {
      // pass, this is rendered as an iframe, we don't reach in for now.
    } else if (panelId == 'Card') {
      // pass for now.
      // TODO: But we should click each tab and recursively check its content!
    } else if (panelId === 'dir') {
      cy.wrap(panel).find('table').should('exist');
    } else if (panelId == 'pil-image') {
      cy.wrap(panel)
        .find('img')
        .should('exist')
        .and($img => {
          // "naturalWidth" and "naturalHeight" are set when the image loads
          expect($img[0].naturalWidth).to.be.greaterThan(0);
        });
    } else if (panelId == 'Color') {
      cy.wrap(panel).should('have.css', 'background-color');
    } else if (panelId === 'string' || panelId === 'number') {
      // just existence of the data-test-weave-id is enough
    } else {
      throw new Error(
        `Unknown weave panel type (${panelId}). You should add assertions for it.`
      );
    }
  });
}

// Log the full error output. From here: https://github.com/cypress-io/cypress/issues/5470
const exec = (command: string) => {
  cy.exec(command, {failOnNonZeroExit: false}).then(result => {
    if (result.code) {
      throw new Error(`Execution of "${command}" failed
      Exit code: ${result.code}
      Stdout:\n${result.stdout}
      Stderr:\n${result.stderr}`);
    }
  });
};

function executeNotebook(notebookPath: string) {
  exec(
    'pytest --nbmake --nbmake-timeout=30000 --overwrite "' + notebookPath + '"'
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
      checkNotebookOutputsExist();
      cy.wait(1000);
      checkNotebookOutputsExist();
    });
  });
}
