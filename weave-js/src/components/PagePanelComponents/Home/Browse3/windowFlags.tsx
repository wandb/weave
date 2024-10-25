/**
 * Feature Flag Management Utility
 *
 * This module provides a simple feature flag management system for toggling beta features.
 * It allows developers to specify a list of flags, get the current state of any given flag,
 * and enables users to toggle flags via the browser console.
 *
 * Usage:
 * 1. Initialize flags at the app's entry point:
 *    import { initializeFlags } from './windowFlags';
 *    initializeFlags(['BETA_FEATURE_1', 'BETA_FEATURE_2']);
 *
 * 2. Use the hook in React components:
 *    import { useFeatureFlag } from './windowFlags';
 *    const MyComponent = () => {
 *      const isBetaFeature1Enabled = useFeatureFlag('BETA_FEATURE_1');
 *      return isBetaFeature1Enabled ? <BetaFeature1 /> : null;
 *    };
 *
 * 3. Toggle flags from the browser console:
 *    window.setFeatureFlag('BETA_FEATURE_1', true);
 *
 * This system allows for easy management of feature flags and real-time updates
 * in React components when flags are toggled.
 */

import {useEffect, useState} from 'react';

// Define the type for the flags
type FeatureFlags = {
  [key: string]: boolean;
};

// Initialize the flags on the window object
declare global {
  interface Window {
    featureFlags: FeatureFlags;
    setFeatureFlag: (flagName: string, value: boolean) => void;
  }
}

// Initialize the feature flags
const initializeFeatureFlags = (flags: string[]) => {
  window.featureFlags = flags.reduce((acc, flag) => {
    acc[flag] = false;
    return acc;
  }, {} as FeatureFlags);

  // Expose a method to set flags
  window.setFeatureFlag = (flagName: string, value: boolean) => {
    if (flagName in window.featureFlags) {
      window.featureFlags[flagName] = value;
      // Dispatch a custom event when a flag is changed
      window.dispatchEvent(
        new CustomEvent('featureFlagChanged', {detail: {flagName, value}})
      );
    } else {
      console.warn(`Feature flag "${flagName}" is not defined.`);
    }
  };
};

// Function to get the current state of a flag
export const getFeatureFlag = (flagName: string): boolean => {
  return window.featureFlags?.[flagName] ?? false;
};

// React hook to use feature flags in components
export const useFeatureFlag = (flagName: string): boolean => {
  const [flagValue, setFlagValue] = useState(getFeatureFlag(flagName));

  useEffect(() => {
    const handleFlagChange = (event: CustomEvent) => {
      if (event.detail.flagName === flagName) {
        setFlagValue(event.detail.value);
      }
    };
    window.addEventListener(
      'featureFlagChanged',
      handleFlagChange as EventListener
    );

    return () => {
      window.removeEventListener(
        'featureFlagChanged',
        handleFlagChange as EventListener
      );
    };
  }, [flagName]);

  return flagValue;
};

// Function to initialize the feature flags
export const initializeFlags = (flags: string[]) => {
  initializeFeatureFlags(flags);
};

export const ENABLE_ONLINE_EVAL_UI = 'ENABLE_ONLINE_EVAL_UI';
initializeFlags([ENABLE_ONLINE_EVAL_UI]);

// Set the feature flag to true for testing
window.setFeatureFlag('ENABLE_ONLINE_EVAL_UI', true);
