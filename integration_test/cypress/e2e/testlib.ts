// Log the full error output. From here: https://github.com/cypress-io/cypress/issues/5470
export const exec = (command: string, timeout: number) => {
  return cy.exec(command, {failOnNonZeroExit: false, timeout}).then(result => {
    if (result.code) {
      throw new Error(`Execution of "${command}" failed
      Exit code: ${result.code}
      Stdout:\n${result.stdout}
      Stderr:\n${result.stderr}`);
    }
  });
};

export function checkAllPanelsRendered() {
  const panels = cy
    .get('[data-test-weave-id]', {timeout: 60000})
    .should('have.length.greaterThan', 0);
  panels.each((panel, index) => {
    // assert that the element has a non-empty attribute 'data-test-weave-id'
    const panelId = panel.attr('data-test-weave-id');
    if (panelId == 'PanelPlotly') {
      cy.wrap(panel).find('.plotly', {timeout: 30000}).should('exist');
    } else if (panelId == 'table') {
      cy.wrap(panel).find('.BaseTable').should('exist');
    } else if (panelId === 'plot') {
      cy.wrap(panel).find('canvas').should('exist');
    } else if (panelId == 'html-file') {
      // pass, this is rendered as an iframe, we don't reach in for now.
    } else if (panelId == 'boolean') {
      // pass for now, boolean just renders its value
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

export const getPanel = (path: string[]) => {
  const attrPath = path.map(p => `[data-weavepath=${p}]`);
  return cy.get(attrPath.join(' '));
};
