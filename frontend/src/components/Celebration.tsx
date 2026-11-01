import React, { useEffect } from 'react';
import { PartyPopper } from 'lucide-react';
import styles from './Celebration.module.css';

interface CelebrationProps {
  show: boolean;
  title: string;
  subtitle?: string;
  onDone?: () => void;
}

const PIECES = Array.from({ length: 18 }, (_, index) => ({
  id: index,
  left: 6 + ((index * 53) % 88),
  delay: (index % 6) * 0.06,
  duration: 1.8 + (index % 5) * 0.18,
  rotate: (index * 47) % 360,
  tone: index % 3,
}));

export const Celebration: React.FC<CelebrationProps> = ({ show, title, subtitle, onDone }) => {
  useEffect(() => {
    if (!show) return;
    const timer = window.setTimeout(() => onDone?.(), 3600);
    return () => window.clearTimeout(timer);
  }, [show, onDone]);

  if (!show) return null;

  return (
    <div className={styles.layer} aria-live="polite">
      <div className={styles.confetti} aria-hidden="true">
        {PIECES.map((piece) => (
          <span
            key={piece.id}
            className={`${styles.piece} ${styles[`tone${piece.tone}`]}`}
            style={{
              left: `${piece.left}%`,
              animationDelay: `${piece.delay}s`,
              animationDuration: `${piece.duration}s`,
              transform: `rotate(${piece.rotate}deg)`,
            }}
          />
        ))}
      </div>
      <div className={styles.banner}>
        <span className={styles.icon}>
          <PartyPopper size={20} />
        </span>
        <div>
          <strong>{title}</strong>
          {subtitle && <p>{subtitle}</p>}
        </div>
      </div>
    </div>
  );
};
