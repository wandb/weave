import {useEffect, useState} from 'react';

// This hook is copied from core
// Its function is to determine if the navbar is within the viewport
export function useHandleScroll(): {scrolled: boolean; scrollWidth: number} {
  const [scrolled, setScrolled] = useState(false);
  const [scrollWidth, setScrollWidth] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const scrollPosition = window.scrollY;
      setScrolled(scrollPosition >= 60);
      setScrollWidth(scrollPosition);
    };

    window.addEventListener('scroll', handleScroll);

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, []);

  return {scrolled, scrollWidth};
}
