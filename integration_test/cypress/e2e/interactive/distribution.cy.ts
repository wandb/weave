import {exec, getPanel, openPanelConfig} from '../testlib';

describe('distribution interactions', () => {
  it('can configure a python panel from scratch by clicking', () => {
    exec('python cypress/e2e/interactive/distribution.py', 10000).then(
      result => {
        const url = result.stdout.replace(
          'http://localhost:9994/__frontend/weave_jupyter',
          ''
        );

        cy.on('uncaught:exception', (err, runnable) => {
          if (err.message.includes('ResizeObserver loop')) {
            return false;
          }
        });

        cy.visit(url);
        cy.wait(1000);

        const panel = getPanel(['main', 'panel0']);
        openPanelConfig(panel);
        cy.wait(1000);

        const value = '(item) => item["loss1"]';

        cy.get('[data-test=weave-sidebar]')
          .find(
            '[data-test=expression-editor-container] [contenteditable=true]'
          )
          .contains(value);

        // modify the expression to select some data.
        // this is currently broken. it fails with an error
        // in mutation.ts. todo: renable when we want declarable
        // python panels to work again.
        /*

          .click()
          .type('{rightarrow}'.repeat(value.length))
          .type('{backspace}'.repeat(9))
          .type("['loss2']")
          .type('{enter}');

          */

        // Click ok in the sidebar
        cy.get('[data-testid=close-panel-panel-config]').click();

        cy.get('rect').should('have.length.gte', 2);
      }
    );
  });
});
