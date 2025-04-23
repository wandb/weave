// Originally was in Links.tsx but that caused a circular dependency
export const opNiceName = (opName: string) => {
  let text = opName;
  if (text.startsWith('op-')) {
    text = text.slice(3);
  }
  return text;
};
