import React from 'react';
import { Sparkles, ArrowRight } from 'lucide-react';
import { AuthModal } from '../../components/AuthModal';
import styles from './WelcomeHero.module.css';

interface WelcomeHeroProps {
  openTour: () => void;
  isAuthModalOpen: boolean;
  onOpenAuth: () => void;
  onCloseAuth: () => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({
  openTour,
  isAuthModalOpen,
  onOpenAuth,
  onCloseAuth,
}) => {
  return (
    <div className={styles.welcomeContainer}>
      <section className={styles.welcomeHero}>
        <div className={styles.welcomeCopy}>
          <span className={styles.welcomeBadge}>Built for classes 6–10</span>
          <h1 className={styles.welcomeTitle}>
            Your books.
            <br />
            <span className={styles.welcomeTitleAccent}>Your pace.</span> Your next step.
          </h1>
          <p className={styles.welcomeSubtitle}>
            SETU turns the textbooks and notes you already own into lessons, practice and
            grounded answers — then adapts to what you actually get right.
          </p>
          <div className={styles.welcomeActions}>
            <button type="button" className={styles.welcomePrimaryBtn} onClick={openTour}>
              Get Started <ArrowRight size={17} />
            </button>
            <button
              type="button"
              className={styles.welcomeSecondaryBtn}
              onClick={onOpenAuth}
            >
              I have an account
            </button>
          </div>
          <ul className={styles.welcomeTrust} aria-label="What SETU offers">
            <li>Source-grounded answers</li>
            <li>Works offline</li>
            <li>Adapts to your evidence</li>
          </ul>
        </div>

        <div className={styles.welcomeArt} aria-hidden="true">
          <div className={styles.artCardBack} />
          <div className={styles.artCard}>
            <span className={styles.artTag}>Unit 01</span>
            <strong>Your chapter</strong>
            <span className={styles.artLine} />
            <span className={styles.artLineShort} />
            <div className={styles.artChips}>
              <span>Read</span>
              <span>Practice</span>
              <span>Checkpoint</span>
            </div>
          </div>
          <div className={styles.artBubble}>
            <Sparkles size={15} /> Page-cited
          </div>
          <div className={styles.artStar} />
        </div>
      </section>

      <section className={styles.welcomeSteps} aria-label="How SETU works">
        <div className={styles.stepsIntro}>
          <span className={styles.eyebrow}>The desk routine</span>
          <h2 className={styles.stepsTitle}>From a source you own to evidence you can see.</h2>
        </div>
        <ol className={styles.stepSequence}>
          <li className={styles.welcomeStep}>
            <span className={styles.stepNumber}>01</span>
            <div className={styles.stepBody}>
              <h3 className={styles.stepTitle}>Add a source</h3>
              <p className={styles.stepText}>
                Upload a PDF, DOCX, PPTX, text file, or page image you have the right to use.
                SETU keeps the original and indexes the pages it can read.
              </p>
            </div>
          </li>
          <li className={styles.welcomeStep}>
            <span className={styles.stepNumber}>02</span>
            <div className={styles.stepBody}>
              <h3 className={styles.stepTitle}>Review the plan</h3>
              <p className={styles.stepText}>
                Check the chapters found in the source, then choose the class and subject.
                Units are generated only after you approve the plan.
              </p>
            </div>
          </li>
          <li className={styles.welcomeStep}>
            <span className={styles.stepNumber}>03</span>
            <div className={styles.stepBody}>
              <h3 className={styles.stepTitle}>Learn, solve, test</h3>
              <p className={styles.stepText}>
                Read explanations with page citations, work through guided practice with
                progressive hints, then take a checkpoint without hints.
              </p>
            </div>
          </li>
          <li className={styles.welcomeStep}>
            <span className={styles.stepNumber}>04</span>
            <div className={styles.stepBody}>
              <h3 className={styles.stepTitle}>Ask and return</h3>
              <p className={styles.stepText}>
                Ask doubts grounded in the source. Save ready lessons for offline study;
                answers and attempts queued on this device sync when you reconnect.
              </p>
            </div>
          </li>
        </ol>
        <aside className={styles.deskNote}>
          <span className={styles.deskNoteOrb} aria-hidden="true" />
          <h2 className={styles.deskNoteTitle}>No invented evidence</h2>
          <p className={styles.deskNoteText}>
            Lessons cite the pages they came from. If a page cannot be read, SETU names it
            instead of filling the gap. If the source does not contain enough evidence,
            an answer says so.
          </p>
        </aside>
      </section>

      <AuthModal isOpen={isAuthModalOpen} onClose={onCloseAuth} />
    </div>
  );
};
