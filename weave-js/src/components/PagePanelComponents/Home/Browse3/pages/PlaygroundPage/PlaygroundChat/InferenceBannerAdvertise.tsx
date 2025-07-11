import React from 'react';
import {useLocalStorage} from 'react-use';

import {Alert} from '../../../../../../Alert';
import {Button} from '../../../../../../Button';
import {INFERENCE_PATH} from '../../../inference/util';
import {Link} from '../../common/Links';

const USD_FORMATTER = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const formatAsDollars = (amount: number) => {
  return USD_FORMATTER.format(amount);
};

type InferenceBannerAdvertiseProps = {
  inferenceFreeLimit: number;
};

export const InferenceBannerAdvertise = ({
  inferenceFreeLimit,
}: InferenceBannerAdvertiseProps) => {
  const [isHidden, setIsHidden] = useLocalStorage<boolean>(
    `hint.playground.inference.advertise`,
    false
  );
  const onClose = () => {
    setIsHidden(true);
  };
  if (isHidden) {
    return null;
  }

  const limitDollars = inferenceFreeLimit / 100;

  return (
    <div className="mb-16 mt-12 w-[800px]">
      <Alert severity="info">
        <div className="flex items-center gap-12">
          <div>
            <b>New: Test open source models right in Weave!</b>{' '}
            <span>
              Jumpstart your workflows with powerful models, no setup needed.
              For a limited time, get {formatAsDollars(limitDollars)} in monthly
              credits.
            </span>
          </div>
          <Link className="whitespace-nowrap" to={INFERENCE_PATH}>
            Browse all models
          </Link>
          <Button variant="ghost" icon="close" onClick={onClose} />
        </div>
      </Alert>
    </div>
  );
};
