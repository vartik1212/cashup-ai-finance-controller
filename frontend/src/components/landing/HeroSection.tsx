import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ArrowDown } from 'lucide-react';

export const HeroSection: React.FC = () => {
  const scrollToHowItWorks = (e: React.MouseEvent) => {
    e.preventDefault();
    const el = document.getElementById('how-it-works');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <section
      id="hero"
      className="relative min-h-screen w-full flex flex-col justify-center items-center px-6 sm:px-8 pt-24 pb-16 overflow-hidden select-none"
    >
      {/* Three extremely subtle background data paths with spatial perspective */}
      <div
        aria-hidden="true"
        className="absolute inset-0 pointer-events-none flex items-center justify-center opacity-25 z-0"
        style={{
          perspective: '1000px',
          transformStyle: 'preserve-3d',
        }}
      >
        <svg
          viewBox="0 0 1200 800"
          className="w-full h-full max-w-6xl text-[#1E2D47] stroke-current"
          fill="none"
          strokeWidth="1"
          style={{ transform: 'rotateX(35deg) translateZ(-80px)' }}
        >
          {/* Path 1: Invoices */}
          <path
            d="M 200 100 C 200 350, 450 500, 600 700"
            strokeDasharray="4 8"
            className="opacity-40"
          />
          <text x="210" y="140" fill="#91A0B6" fontSize="10" fontFamily="monospace" opacity="0.4">
            SOURCE.INVOICES [ERP]
          </text>

          {/* Path 2: Settlements */}
          <path
            d="M 600 80 C 600 320, 600 500, 600 700"
            strokeDasharray="4 8"
            className="opacity-50"
          />
          <text x="615" y="120" fill="#91A0B6" fontSize="10" fontFamily="monospace" opacity="0.4">
            SOURCE.SETTLEMENTS [GATEWAY]
          </text>

          {/* Path 3: Bank */}
          <path
            d="M 1000 100 C 1000 350, 750 500, 600 700"
            strokeDasharray="4 8"
            className="opacity-40"
          />
          <text x="880" y="140" fill="#91A0B6" fontSize="10" fontFamily="monospace" opacity="0.4">
            SOURCE.BANK [STATEMENT]
          </text>

          {/* Subtle convergence junction ring */}
          <circle cx="600" cy="700" r="16" stroke="#22D3EE" strokeWidth="1.2" opacity="0.3" strokeDasharray="3 3" />
        </svg>
      </div>

      {/* Main Hero Content: Clean, uncluttered, commanding typography */}
      <div className="relative z-20 max-w-4xl mx-auto text-center flex flex-col items-center">

        {/* Large Headline (Maximum around 2 lines on desktop) */}
        <h1 className="text-4xl sm:text-6xl lg:text-7xl font-semibold tracking-tight text-[#F4F7FB] leading-[1.08] max-w-3xl mb-6">
          Reconciliation,
          <br />
          <span className="text-[#91A0B6]">without the guesswork.</span>
        </h1>

        {/* Supporting Copy */}
        <div className="text-base sm:text-lg text-[#91A0B6] font-normal leading-relaxed max-w-xl mb-10 space-y-1">
          <p>Match invoices, settlements and bank transactions.</p>
          <p>Verify the evidence. Surface what needs attention.</p>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row items-center gap-4 mb-12">
          <Link
            to="/app"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2.5 px-6 py-3.5 rounded-xl bg-[#6C5CE7] hover:bg-[#5b4bc4] text-sm font-medium text-[#F4F7FB] shadow-[0_4px_24px_rgba(108,92,231,0.3)] hover:shadow-[0_6px_32px_rgba(108,92,231,0.45)] transition-all duration-200 cursor-pointer active:scale-[0.98]"
          >
            <span>Launch CashUP</span>
            <ArrowRight size={15} className="text-[#F4F7FB]/90" />
          </Link>

          <a
            href="#how-it-works"
            onClick={scrollToHowItWorks}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3.5 rounded-xl bg-[#101A2B] hover:bg-[#16233B] border border-[#1F2E47] hover:border-[#2D4163] text-sm font-medium text-[#91A0B6] hover:text-[#F4F7FB] transition-all duration-200 cursor-pointer"
          >
            <span>See how it works</span>
            <ArrowDown size={14} className="text-[#91A0B6]" />
          </a>
        </div>

        {/* Trust Statement */}
        <div className="flex items-center gap-2 text-xs font-mono text-[#91A0B6]/80 pt-2 border-t border-[#1F2E47]/50">
          <span className="w-1 h-1 rounded-full bg-[#2DD4A7]" />
          <span>AI investigates. Deterministic financial logic verifies.</span>
        </div>
      </div>
    </section>
  );
};
