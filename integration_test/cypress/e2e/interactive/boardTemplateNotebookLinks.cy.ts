import {goToHomePage} from '../testlib';

describe('board template notebook links', () => {
  it('check that board template notebook links to colab work', () => {
    goToHomePage();
    cy.contains('Board templates').click();

    cy.get('[data-testid="template-card"]').each(($el, index, $list) => {
      cy.wrap($el)
        .trigger('mouseenter')
        .realHover()
        .trigger('mouseenter')
        .realHover()
        .contains('Try it out')
        .click();

      cy.get(
        'img[src="https://colab.research.google.com/assets/colab-badge.svg"]'
      )
        .parent('a')
        .each(($innerEl, index, $list) => {
          const href = $innerEl.prop('href');
          // check that the url starts with https://colab.research.google.com/github
          expect(href).to.match(
            /^https:\/\/colab\.research\.google\.com\/github/
          );

          // replace with url of actual notebook. this is a hack
          // because we can't actually make assertions on the notebook
          // due to cross-origin restrictions in cypress. this checks
          // that the notebook is available by making the request
          // that colab would make to load the notebook.
          const newHref = href
            .replace(
              'https://colab.research.google.com/github',
              'https://raw.githubusercontent.com'
            )
            .replace('blob/', '');

          // load the notebook.
          cy.request(newHref).then(response => {
            // check that the status code is 200
            expect(response.status).to.eq(200);
          });
        });
    });
  });
});
