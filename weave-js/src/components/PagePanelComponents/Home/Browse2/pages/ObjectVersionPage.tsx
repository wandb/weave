import React, {useMemo} from 'react';
import {Link} from 'react-router-dom';

import {Browse2ObjectVersionItemComponent} from '../Browse2ObjectVersionItemPage';
import {useEPPrefix} from './util';

export const ObjectVersionPage: React.FC<{
  entity: string;
  project: string;
  objectName: string;
  digest: string;
}> = props => {
  const prefix = useEPPrefix();
  const params = useMemo(() => {
    return {
      entity: props.entity,
      project: props.project,
      rootType: 'UNKNOWN',
      objName: props.objectName,
      objVersion: props.digest,
    };
  }, [props.digest, props.entity, props.objectName, props.project]);
  return <Browse2ObjectVersionItemComponent params={params} />;
};

/*
<div>
      <h1>ObjectVersionPage Placeholder</h1>
      <div>
        This is the detail page for ObjectVersion. A ObjectVersion is a
        "version" of a saved weave object. In the user's mind it is analogous to
        a specific instance.
      </div>
      <div>Migration Notes:</div>
      <ul>
        <li>
          Weaveflow pretty much already has this page (
          <a href="https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset/696d98783ec24548e08b">
            https://weave.wandb.test/browse2/dannygoldstein/hooman-eval-notion2/Dataset/eval_dataset/696d98783ec24548e08b
          </a>
          ) that includes most of what we will want here. However, this is one
          of the most important pages, so it is is worth enumerating the primary
          features
        </li>
      </ul>
      <div>Primary Features:</div>
      <ul>
        <li>Property Values (possibly editable)</li>
        <li>(future) Objet/Call DAG Visual</li>
      </ul>
      <div>Links:</div>
      <ul>
        <li>
          Link to parent TypeVersion ({' '}
          <Link to={prefix('/types/type_name/versions/version_id')}>
            /types/[type_name]/versions/[version_id]
          </Link>
          )
        </li>
        <li>
          Link to parent Object ({' '}
          <Link to={prefix('/objects/object_name')}>
            /objects/[object_name]
          </Link>
          )
        </li>
        <li>
          Link to Producing Call ({' '}
          <Link to={prefix('/calls/call_id')}>/calls/call_id</Link>)
        </li>
        <li>
          Link to all Consuming Calls ({' '}
          <Link to={prefix('/calls?filter=uses=object_version_id')}>
            /types/[type_name]/versions/[version_id]
          </Link>
          )
        </li>
      </ul>
      <div>Inspiration</div>
      Existing Weaveflow Page
      <br />
      <img
        src="https://github.com/wandb/weave/blob/a0d44639b972421890ed6149f9cbc01211749291/weave-js/src/components/PagePanelComponents/Home/Browse2/pages/example_media/objectversion_example.png?raw=true"
        style={{
          width: '100%',
        }}
        alt=""
      />
    </div>
    */
