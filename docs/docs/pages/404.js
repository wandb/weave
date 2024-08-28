import React, { useEffect } from 'react';
import { Redirect } from '@docusaurus/router';

export default function NotFound() {
  useEffect(() => {
    window.location.href = '/';
  }, []);

  return <Redirect to="/" />;
}
