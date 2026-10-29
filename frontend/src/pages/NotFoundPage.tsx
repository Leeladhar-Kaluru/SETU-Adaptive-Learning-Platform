import React from 'react';
import { Link } from 'react-router-dom';
import styles from './NotFoundPage.module.css';

export const NotFoundPage: React.FC = () => {
  return (
    <section className={styles.page}>
      <p className={styles.eyebrow}>SETU</p>
      <h1>Page not found</h1>
      <p className={styles.lede}>
        This route does not exist. It may have been removed, or the address may be mistyped.
      </p>
      <Link to="/" className={styles.link}>
        Back to SETU
      </Link>
    </section>
  );
};
