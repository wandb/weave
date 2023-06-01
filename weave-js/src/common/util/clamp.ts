type ClampParams = {
  min?: number;
  max?: number;
};

export default function clamp(value: number, {min, max}: ClampParams) {
  let clampedValue = value;
  if (min != null) {
    clampedValue = Math.max(clampedValue, min);
  }
  if (max != null) {
    clampedValue = Math.min(clampedValue, max);
  }
  return clampedValue;
}
