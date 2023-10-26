import {config} from 'cypress/types/bluebird';

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

export const openPanelConfig = (panel: Cypress.Chainable) => {
  panel.trigger('mouseenter').click();
  const editorPanel = panel.find('[data-testid="open-panel-editor"]');
  editorPanel.click();
  return editorPanel;
};

export const gotoBlankDashboard = () => {
  exec('python cypress/e2e/interactive/blank.py', 10000);
  const url =
    '/?fullScreen&expNode=%7B%22nodeType%22%3A%20%22output%22%2C%20%22type%22%3A%20%22any%22%2C%20%22fromOp%22%3A%20%7B%22name%22%3A%20%22get%22%2C%20%22inputs%22%3A%20%7B%22uri%22%3A%20%7B%22nodeType%22%3A%20%22const%22%2C%20%22type%22%3A%20%22string%22%2C%20%22val%22%3A%20%22local-artifact%3A///dashboard-list%3Alatest/obj%22%7D%7D%7D%7D';
  cy.viewport(1600, 900);
  cy.visit(url);
  cy.get('canvas').should('be.visible');
  cy.get('[data-testid="header-center-controls"]').should('be.visible').click();
  cy.get('[data-testid="new-board-button"]').should('be.visible').click();
};

export const goToHomePage = () => {
  const url = '/';
  cy.viewport(1600, 900);
  cy.visit(url);
  cy.contains('Board templates').should('be.visible');
};

export const addSidebarPanel = () => {
  getPanel(['sidebar']).contains('New variable').click();
};

export const addMainPanel = () => {
  getPanel(['main'])
    .find('button[data-test="new-panel-button"]')
    .click({force: true});
};

export const dashboardConvertToControl = (path: string[]) => {
  const panel = getPanel(path);
  panel.find('i.sliders').click();
};

export const panelTypeInputExpr = (path: string[], text: string) => {
  const panel = getPanel(path);
  panel
    .find('[data-test=expression-editor-container] [contenteditable=true]')
    .click()
    .clear()
    .type(text)
    .wait(300)
    .type('{enter}', {force: true});
};

export const scrollToEEAndType = (path: string[], text: string) => {
  const panel = getPanel(path);

  const ee = panel
    .trigger('mouseenter')
    .click()
    .find('[data-test=expression-editor-container] [contenteditable=true]');

  let currentText: string = '';
  for (let i = 0; i < 15; i++) {
    ee.invoke('text').then(t => {
      currentText = t;
    });

    if (currentText === text) {
      break;
    }

    ee.realHover()
      .realClick()

      .type(text, {force: true})
      .wait(300)
      .type('{enter}', {force: true});
  }
};

export const panelChangeId = (path: string[], text: string) => {
  const panel = getPanel(path);
  panel.find('[data-test-comp=PanelNameEditor] [contenteditable=true]').click();
  cy.get('[data-test=wb-menu-item]').contains(text).click();
};

export const tableAppendColumn = (path: string[], expr) => {
  const panel = getPanel(path);
  panel.find('i.column-actions-trigger').click({force: true});
  // TODO: these should be panel.find... but that didn't work on my first try
  cy.get('[data-test=wb-menu-item]').contains('Insert 1 right').click();
  cy.get('[data-test=column-header').last().click();

  cy.get('.wb-table-action-popup')
    .find('[data-test=expression-editor-container] [contenteditable=true]')
    .click()
    .type('{backspace}{backspace}{backspace}{backspace}{backspace}')
    .type(expr);
  cy.get('#root').click({force: true});
};

export const tableCheckContainsValue = (path: string[], value: string) => {
  const panel = getPanel(path);
  panel.find('.BaseTable__row-cell div').contains(value);
};

export const sliderSetValue = (path: string[], value: number) => {
  const panel = getPanel(path);
  panel.find('input[type=range]').invoke('val', value).trigger('input');
};

export const setPlotConfig = (
  configDivElement: Cypress.Chainable,
  eeText: string
) => {
  configDivElement
    .find('[data-test=expression-editor-container] [contenteditable=true]')
    .click()
    .clear()
    .type(eeText)
    .wait(300)
    .type('{enter}', {force: true});
};
