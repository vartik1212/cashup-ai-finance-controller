import React from 'react';
import { ArrowDown, AlertTriangle } from 'lucide-react';

export const KnowWhenNotToGuessSection: React.FC = () => {
  return (
    <section className="relative w-full py-28 sm:py-36 px-6 sm:px-8 border-t border-[#1F2E47]/50 bg-[#07111F] overflow-hidden">
      <div className="max-w-5xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
          
          {/* Left Side: Commanding typography & authoritative philosophy */}
          <div className="lg:col-span-7">
            <div className="inline-block text-[11px] font-mono tracking-widest text-[#91A0B6] uppercase mb-4">
              PHASE 03 — DETERMINISTIC TRUTH
            </div>
            
            <h2 className="text-3xl sm:text-5xl font-semibold tracking-tight text-[#F4F7FB] leading-[1.12] mb-6">
              AI investigates.
              <br />
              <span className="text-[#91A0B6]">Financial logic verifies.</span>
            </h2>

            <p className="text-sm sm:text-base text-[#91A0B6] leading-relaxed max-w-lg mb-8">
              CashUP can explain evidence and investigate exceptions, but deterministic rules remain authoritative for financial verification.
            </p>

            <div className="p-4 rounded-xl bg-[#101A2B]/60 border border-[#1F2E47] inline-block">
              <div className="text-xs font-mono text-[#F4F7FB] font-medium">
                Core Guardrail: Zero hallucinated reconciliation
              </div>
              <div className="text-[11px] text-[#91A0B6] mt-1 font-mono">
                Exceptions are preserved with complete lineage, never papered over.
              </div>
            </div>
          </div>

          {/* Right Side: Minimal Evidence Stack layered in Z-space */}
          <div
            className="lg:col-span-5 flex flex-col items-center"
            style={{ perspective: '900px' }}
          >
            <div
              className="w-full max-w-xs space-y-2.5 transition-transform duration-300"
              style={{
                transformStyle: 'preserve-3d',
                transform: 'rotateX(5deg) rotateY(-4deg)',
              }}
            >
              {/* Card 1: Invoice */}
              <div className="p-3.5 rounded-xl bg-[#101A2B] border border-[#1F2E47] shadow-[0_8px_24px_rgba(5,11,20,0.5)]">
                <div className="flex items-center justify-between text-[11px] font-mono text-[#91A0B6] mb-1">
                  <span>INVOICE</span>
                  <span className="text-[#F4F7FB]">AR/26/4115</span>
                </div>
                <div className="text-sm font-mono font-bold text-[#F4F7FB]">
                  ₹9,18,000
                </div>
              </div>

              {/* Connector arrow */}
              <div className="flex justify-center -my-1 text-[#91A0B6]/60">
                <ArrowDown size={13} />
              </div>

              {/* Card 2: Settlement */}
              <div className="p-3.5 rounded-xl bg-[#101A2B] border border-[#1F2E47] shadow-[0_8px_24px_rgba(5,11,20,0.5)]">
                <div className="flex items-center justify-between text-[11px] font-mono text-[#91A0B6] mb-1">
                  <span>SETTLEMENT</span>
                  <span className="text-[#F4F7FB]">SET-88421</span>
                </div>
                <div className="text-sm font-mono font-bold text-[#F4F7FB]">
                  ₹8,74,500
                </div>
              </div>

              {/* Connector arrow */}
              <div className="flex justify-center -my-1 text-[#91A0B6]/60">
                <ArrowDown size={13} />
              </div>

              {/* Card 3: Variance breakdown */}
              <div className="p-3.5 rounded-xl bg-[#0E1726] border border-[#1F2E47] shadow-[0_8px_24px_rgba(5,11,20,0.5)]">
                <div className="flex items-center justify-between text-[11px] font-mono text-[#91A0B6] mb-1">
                  <span>VARIANCE</span>
                  <span className="text-[#F4B740]">Gateway MDR Deducted</span>
                </div>
                <div className="text-sm font-mono font-bold text-[#F4B740]">
                  ₹43,500
                </div>
              </div>

              {/* Connector arrow */}
              <div className="flex justify-center -my-1 text-[#91A0B6]/60">
                <ArrowDown size={13} />
              </div>

              {/* Card 4: Confidence Score */}
              <div className="p-3.5 rounded-xl bg-[#0E1726] border border-[#1F2E47] shadow-[0_8px_24px_rgba(5,11,20,0.5)]">
                <div className="flex items-center justify-between text-[11px] font-mono text-[#91A0B6] mb-1">
                  <span>CONFIDENCE</span>
                  <span className="text-[#F4F7FB]">Rule Engine</span>
                </div>
                <div className="text-sm font-mono font-bold text-[#F4F7FB]">
                  70%
                </div>
              </div>

              {/* Connector arrow */}
              <div className="flex justify-center -my-1 text-[#91A0B6]/60">
                <ArrowDown size={13} />
              </div>

              {/* Card 5: Outcome Classification (Restrained Amber) */}
              <div className="p-4 rounded-xl bg-[#F4B740]/10 border border-[#F4B740]/40 shadow-[0_8px_24px_rgba(244,183,64,0.1)]">
                <div className="flex items-center gap-2 text-xs font-mono font-bold text-[#F4B740]">
                  <AlertTriangle size={14} className="text-[#F4B740]" />
                  <span>REVIEW REQUIRED</span>
                </div>
                <div className="text-[10px] font-mono text-[#91A0B6] mt-1">
                  Isolated for controller approval with AI lineage explanation.
                </div>
              </div>

            </div>
          </div>

        </div>

        {/* Visually Important Anchoring Statement at Bottom */}
        <div className="mt-20 pt-10 border-t border-[#1F2E47]/60 text-center">
          <p className="text-lg sm:text-2xl font-medium tracking-tight text-[#F4F7FB] max-w-2xl mx-auto">
            “CashUP never turns uncertainty into a confident answer.”
          </p>
          <div className="text-xs font-mono text-[#91A0B6] mt-2">
            Deterministic Rule Authority · Full Explainability Audit Trail
          </div>
        </div>

      </div>
    </section>
  );
};
