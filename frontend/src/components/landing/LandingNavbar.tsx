import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { GitMerge, ArrowRight } from 'lucide-react';

export const LandingNavbar: React.FC = () => {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 30);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToSection = (e: React.MouseEvent<HTMLAnchorElement>, id: string) => {
    e.preventDefault();
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-[#07111F]/85 backdrop-blur-md border-b border-[#1A263D]/80 py-3.5 shadow-[0_10px_30px_rgba(5,11,20,0.5)]'
          : 'bg-transparent border-b border-transparent py-5'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 sm:px-8 flex items-center justify-between">
        {/* Left: Brand Identity */}
        <Link
          to="/"
          className="flex items-center gap-3 group text-left cursor-pointer focus:outline-none"
        >
          <div className="w-8 h-8 rounded-lg bg-[#101A2B] border border-[#1F2E47] flex items-center justify-center transition-colors group-hover:border-[#6C5CE7]/60 group-hover:bg-[#16233B]">
            <GitMerge size={15} className="text-[#22D3EE] transition-transform duration-300 group-hover:scale-105" />
          </div>
          <div>
            <span className="text-sm font-bold tracking-tight text-[#F4F7FB] block leading-none">
              CashUP
            </span>
            <span className="text-[10px] font-mono text-[#91A0B6] tracking-wider uppercase block mt-1 leading-none">
              AI Finance Controller
            </span>
          </div>
        </Link>

        {/* Right: Minimal Navigation Links & Launch App CTA */}
        <div className="flex items-center gap-6 sm:gap-8">
          <nav className="hidden md:flex items-center gap-7 text-xs font-medium text-[#91A0B6]">
            <a
              href="#how-it-works"
              onClick={(e) => scrollToSection(e, 'how-it-works')}
              className="hover:text-[#F4F7FB] transition-colors cursor-pointer"
            >
              How it works
            </a>
            <a
              href="#architecture"
              onClick={(e) => scrollToSection(e, 'architecture')}
              className="hover:text-[#F4F7FB] transition-colors cursor-pointer"
            >
              Architecture
            </a>
            <a
              href="#proof"
              onClick={(e) => scrollToSection(e, 'proof')}
              className="hover:text-[#F4F7FB] transition-colors cursor-pointer"
            >
              Proof
            </a>
          </nav>

          {/* The ONLY prominent CTA button */}
          <Link
            to="/app"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[#6C5CE7] hover:bg-[#5b4bc4] text-xs font-medium text-[#F4F7FB] shadow-[0_4px_16px_rgba(108,92,231,0.25)] hover:shadow-[0_6px_22px_rgba(108,92,231,0.38)] transition-all duration-200 cursor-pointer active:scale-[0.98]"
          >
            <span>Launch App</span>
            <ArrowRight size={13} className="text-[#F4F7FB]/90 transition-transform duration-200 group-hover:translate-x-0.5" />
          </Link>
        </div>
      </div>
    </header>
  );
};
