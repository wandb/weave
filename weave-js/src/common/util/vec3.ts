type vec3 = [number, number, number];
export function clamp(value: vec3, [low, high]: vec3) {
  return [
    Math.min(Math.max(value[0], low), high),
    Math.min(Math.max(value[1], low), high),
    Math.min(Math.max(value[2], low), high),
  ] as vec3;
}

// Turns a scalar into a vector
export function makeVec3(x: number) {
  return [x, x, x] as vec3;
}

export function add(x: vec3, y: vec3) {
  return [x[0] + y[0], x[1] + y[1], x[2] + y[2]] as vec3;
}
export function sub(x: vec3, y: vec3) {
  return [x[0] - y[0], x[1] - y[1], x[2] - y[2]] as vec3;
}

export function mag(x: vec3) {
  return Math.sqrt(x[0] * x[0] + x[1] * x[1] + x[2] * x[2]);
}

export function mul(x: vec3, y: number) {
  return [x[0] * y, x[1] * y, x[2] * y] as vec3;
}
