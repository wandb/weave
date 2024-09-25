import React, { useState, useRef, useEffect } from 'react';
import styles from './styles.module.css';
import clsx from 'clsx';

export const DesktopWindow = ({ images, alt }) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const carouselRef = useRef(null);

  const handleScroll = () => {
    if (carouselRef.current) {
      const scrollPosition = carouselRef.current.scrollLeft;
      const imageWidth = carouselRef.current.offsetWidth;
      const newIndex = Math.round(scrollPosition / imageWidth);
      setCurrentIndex(newIndex);
    }
  };

  useEffect(() => {
    const carousel = carouselRef.current;
    if (carousel) {
      carousel.addEventListener('scroll', handleScroll);
      return () => carousel.removeEventListener('scroll', handleScroll);
    }
  }, []);

  const scrollToImage = (index) => {
    if (carouselRef.current) {
      const imageWidth = carouselRef.current.offsetWidth;
      carouselRef.current.scrollTo({
        left: index * imageWidth,
        behavior: 'smooth'
      });
    }
  };

  if (!Array.isArray(images) || images.length === 0) {
    return null;
  }

  return (
    <div className={styles['window-content']}>
      <div ref={carouselRef} className={styles['carousel']}>
        <div className={styles['carousel-inner']}>
          {images.map((src, index) => (
            <div key={index} className={styles['carousel-item']}>
              <img 
                src={src} 
                alt={`${alt} ${index + 1}`}
                className={styles['carousel-image'] + " zoomable"}
              />
            </div>
          ))}
        </div>
      </div>
      {images.length > 1 && (
        <div className={styles['carousel-footer']}>
          {images.map((_, index) => (
            <button 
              key={index}
              className={clsx(
                styles['indicator-dot'],
                index === currentIndex && styles['active']
              )}
              onClick={() => scrollToImage(index)}
              aria-label={`Go to image ${index + 1}`}
            />
          ))}
        </div>
      )}
    </div>
  );
};
