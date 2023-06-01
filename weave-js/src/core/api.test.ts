import {constString} from './model/graph/construction';
import {opProjectCreatedAt, opProjectName, opRootProject} from './ops';
import {testClient} from './testUtil';

describe('cg client', () => {
  it('single path subscribe', done => {
    const graph = opProjectName({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('fasion-sweep'),
      }),
    });

    testClient().then(client => {
      const obs = client.subscribe(graph);
      obs.subscribe(result => {
        expect(result).toEqual('fasion-sweep');
        done();
      });
    });
  });

  it('single path query', async () => {
    const graph = opProjectName({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('fasion-sweep'),
      }),
    });

    const client = await testClient();
    const result = await client.query(graph);
    expect(result).toEqual('fasion-sweep');
  });

  it('reuse client for multiple subscriptions', done => {
    const graph1 = opProjectName({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('fasion-sweep'),
      }),
    });

    const graph2 = opProjectCreatedAt({
      project: opRootProject({
        entityName: constString('shawn'),
        projectName: constString('fasion-sweep'),
      }),
    });

    testClient().then(client => {
      const obs1 = client.subscribe(graph1);
      const obs2 = client.subscribe(graph2);
      let doneCount = 0;
      const checkDone = () => ++doneCount === 2 && done();
      obs1.subscribe(result => {
        expect(result).toEqual('fasion-sweep');
        checkDone();
      });
      obs2.subscribe(result => {
        expect(result).toEqual(new Date('2019-03-01T02:44:20.000Z'));
        checkDone();
      });
    });
  });
});
