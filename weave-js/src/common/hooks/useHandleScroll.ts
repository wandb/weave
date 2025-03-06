import {useEffect, useState} from 'react';

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
