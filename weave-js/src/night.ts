let NIGHT_ON = false;

export function nightOn() {
  if (NIGHT_ON) {
    return;
  }
  NIGHT_ON = true;
  const styleElement = document.createElement('style');

  //  https://chat.openai.com/share/6f712e32-d2b7-4445-bf14-70466f59de58
  styleElement.textContent = `body::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 255, 255, 0.1);
        mix-blend-mode: difference;
        pointer-events: none;
        z-index: 9999;
    }
    
    body {
        /* invert colors, increase saturation and apply a hue rotation for a different color scheme */
        filter: invert(1) saturate(2) hue-rotate(200deg);
    }`;
  document.head.appendChild(styleElement);
}
