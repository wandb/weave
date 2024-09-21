import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../weave/legacy/examples/experimental/spacy_demo.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/experimental/spacy_demo.ipynb'
    ));
});
