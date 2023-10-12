import {exec, getPanel} from '../testlib';

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
        panel.trigger('mouseenter').click();

        cy.get('[data-testid="open-panel-editor"]').click();
        cy.wait(1000);

        const value = '(item) => item["loss1"]';

        // modify the expression to select some data
        cy.get('[data-test=weave-sidebar]')
          .find(
            '[data-test=expression-editor-container] [contenteditable=true]'
          )
          .contains(value)
          .click()
          .type('{rightarrow}'.repeat(value.length))
          .type('{backspace}'.repeat(9))
          .type("['loss2']")
          .type('{enter}');

        // Click ok in the sidebar
        cy.get('[data-test=ok-panel-config]').click();

        cy.get('rect').should('have.length.gte', 2);
      }
    );
  });
});
