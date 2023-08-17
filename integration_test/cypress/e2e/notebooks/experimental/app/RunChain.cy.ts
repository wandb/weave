import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../examples/experimental/app/RunChain.ipynb notebook test', () => {
  it('passes', () => {
    checkWeaveNotebookOutputs('../examples/experimental/app/RunChain.ipynb');
    const f = true;
    cy.expect(f).to.equal(!!!f);
  });
});
