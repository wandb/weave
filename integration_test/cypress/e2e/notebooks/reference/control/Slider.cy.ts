import {checkWeaveNotebookOutputs} from '../../notebooks';

describe('../weave/legacy/examples/reference/control/Slider.ipynb notebook test', () => {
  it('passes', () =>
    checkWeaveNotebookOutputs(
      '../weave/legacy/examples/reference/control/Slider.ipynb'
    ));
});
