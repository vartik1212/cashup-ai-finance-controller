import React, { useEffect } from 'react';
import { LandingNavbar } from '../components/landing/LandingNavbar';
import { InteractiveCursorLight } from '../components/landing/InteractiveCursorLight';
import { HeroSection } from '../components/landing/HeroSection';
import { DifferentSourcesSection } from '../components/landing/DifferentSourcesSection';
import { ReconciliationEngineSection } from '../components/landing/ReconciliationEngineSection';
import { ProofSection } from '../components/landing/ProofSection';
import { ProductRevealSection } from '../components/landing/ProductRevealSection';

export const LandingPage: React.FC = () => {
  useEffect(() => {
    // Set document title for landing page
    document.title = 'CashUP — Reconciliation, without the guesswork';
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="relative min-h-screen w-full bg-[#07111F] text-[#F4F7FB] selection:bg-[#6C5CE7]/30 selection:text-[#F4F7FB] overflow-x-clip font-sans">
      {/* Desktop Subtle Interactive Cursor Illumination */}
      <InteractiveCursorLight />

      {/* Minimal Sticky Navigation */}
      <LandingNavbar />

      {/* Main Sequential Narrative Flow */}
      <main className="relative z-10 flex flex-col w-full">
        {/* Section 01: Clean, uncluttered Hero */}
        <HeroSection />

        {/* Section 02: Multi-stream Ingestion Ledgers (Invoices, Settlements, Bank) */}
        <DifferentSourcesSection />

        {/* Section 03: The Main Spatial Reconciliation Engine (MATCH -> VERIFY -> CLASSIFY) */}
        <ReconciliationEngineSection />

        {/* Section 04: Proof, Not Promises (Measured metrics with whitespace) */}
        <ProofSection />

        {/* Final Product Reveal: Straightening dashboard emerging into verified truth & Clean Footer */}
        <ProductRevealSection />
      </main>
    </div>
  );
};
