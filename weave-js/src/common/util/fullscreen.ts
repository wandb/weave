// Fires a callback for a singular event of fullscreen exit
export function onNextExitFullscreen(handler: (...args: any[]) => void) {
  const wrappedHandler = (...args: any[]) => {
    // If
    if (
      !document.fullscreen &&
      !(document as any).mozFullScreenElement &&
      !(document as any).msFullscreenElement
    ) {
      // Call handler with args
      handler(...args);

      document.removeEventListener('webkitfullscreenchange', wrappedHandler);
      document.removeEventListener('mozfullscreenchange', wrappedHandler);
      document.removeEventListener('fullscreenchange', wrappedHandler);
      document.removeEventListener('MSFullscreenChange', wrappedHandler);
    } else {
      // Do nothing
    }
  };

  document.addEventListener('webkitfullscreenchange', wrappedHandler, false);
  document.addEventListener('mozfullscreenchange', wrappedHandler, false);
  document.addEventListener('fullscreenchange', wrappedHandler, false);
  document.addEventListener('MSFullscreenChange', wrappedHandler, false);
}
