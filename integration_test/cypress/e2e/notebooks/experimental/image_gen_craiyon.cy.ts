import {checkWeaveNotebookOutputs} from '../notebooks';

describe('../weave/legacy/examples/experimental/image_gen_craiyon.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/experimental/image_gen_craiyon.ipynb'
    ));
});
