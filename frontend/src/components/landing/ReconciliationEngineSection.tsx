import React, { useEffect, useRef, useState, useMemo } from 'react';

type HoveredNode =
  | 'invoices'
  | 'settlements'
  | 'bank'
  | 'match'
  | 'verify'
  | 'classify'
  | 'auto_verified'
  | 'review_required'
  | 'unresolved'
  | null;

export const ReconciliationEngineSection: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [hoveredNode, setHoveredNode] = useState<HoveredNode>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    let animId: number;

    const handleScroll = () => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalScrollable = rect.height - window.innerHeight;
      if (totalScrollable <= 0) return;

      const progress = Math.max(0, Math.min(1, -rect.top / totalScrollable));
      setScrollProgress(progress);
    };

    const onScroll = () => {
      cancelAnimationFrame(animId);
      animId = requestAnimationFrame(handleScroll);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    handleScroll();

    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(animId);
    };
  }, []);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    setMousePos({ x, y });
  };

  const handleMouseLeave = () => {
    setMousePos({ x: 0, y: 0 });
    setHoveredNode(null);
  };

  // ==========================================
  // NORMALIZED SCROLL STAGE MATH (0.00 -> 1.00)
  // Fully continuous and reversibly scrubbable
  // ==========================================
  const sp = scrollProgress;

  // STAGE 1: Sources Arrive (0.00 -> 0.20)
  // Invoice staggered entrance: 0.00 -> 0.12
  const s1_inv = Math.min(1, Math.max(0, (sp - 0.00) / 0.12));
  // Settlement staggered entrance: 0.03 -> 0.15
  const s1_set = Math.min(1, Math.max(0, (sp - 0.03) / 0.12));
  // Bank staggered entrance: 0.06 -> 0.18
  const s1_bnk = Math.min(1, Math.max(0, (sp - 0.06) / 0.12));

  // STAGE 2: Convergence into MATCH (0.20 -> 0.40)
  const s2_converge = Math.min(1, Math.max(0, (sp - 0.20) / 0.20));

  // STAGE 3: MATCH hands off to VERIFY (0.40 -> 0.58)
  const s3_verify = Math.min(1, Math.max(0, (sp - 0.40) / 0.18));

  // STAGE 4: VERIFY hands off to CLASSIFY (0.58 -> 0.74)
  const s4_classify = Math.min(1, Math.max(0, (sp - 0.58) / 0.16));

  // STAGE 5: Results Fan Out (0.74 -> 0.92)
  const s5_results = Math.min(1, Math.max(0, (sp - 0.74) / 0.18));

  // ==========================================
  // SOURCE CARDS COMPUTED STYLES
  // ==========================================
  // As process advances past 0.40, source cards become quieter (~0.60-0.70 opacity)
  const sourceQuietFactor = sp > 0.40 ? Math.max(0.60, 1 - ((sp - 0.40) / 0.35) * 0.40) : 1;

  // Invoice card: translate from (-25px, -10px) -> (0,0), converges down by +10px in stage 2
  const invYConverge = s2_converge * 10;
  const invStyle = useMemo(() => ({
    opacity: s1_inv * sourceQuietFactor,
    transform: `translate3d(${-25 * (1 - s1_inv)}px, ${-10 * (1 - s1_inv) + invYConverge}px, -8px) scale(${
      (0.98 + 0.02 * s1_inv) * (sp > 0.40 ? 0.98 : 1)
    })`,
  }), [s1_inv, sourceQuietFactor, invYConverge, sp]);

  // Settlement card: translate from (-35px, 0) -> (0,0), middle plane
  const setStyle = useMemo(() => ({
    opacity: s1_set * sourceQuietFactor,
    transform: `translate3d(${-35 * (1 - s1_set)}px, 0px, 0px) scale(${
      (0.98 + 0.02 * s1_set) * (sp > 0.40 ? 0.98 : 1)
    })`,
  }), [s1_set, sourceQuietFactor, sp]);

  // Bank card: translate from (-25px, 10px) -> (0,0), converges up by -10px in stage 2
  const bnkYConverge = -s2_converge * 10;
  const bnkStyle = useMemo(() => ({
    opacity: s1_bnk * sourceQuietFactor,
    transform: `translate3d(${-25 * (1 - s1_bnk)}px, ${10 * (1 - s1_bnk) + bnkYConverge}px, 8px) scale(${
      (1.0 + 0.02 * s1_bnk) * (sp > 0.40 ? 0.98 : 1)
    })`,
  }), [s1_bnk, sourceQuietFactor, bnkYConverge, sp]);

  // ==========================================
  // PROCESS CARD 1: MATCH
  // ==========================================
  const matchMaterialize = Math.min(1, Math.max(0, (sp - 0.20) / 0.16));
  const matchQuiet = sp > 0.40 ? Math.max(0.68, 1 - ((sp - 0.40) / 0.25) * 0.32) : 1;
  const matchActive = sp >= 0.24 && sp < 0.45;
  const matchStatusText = sp < 0.24 ? 'Scanning...' : sp < 0.34 ? '3 candidates' : 'Matched ✓';

  const matchStyle = useMemo(() => {
    const ghostOp = 0.05;
    const baseOp = sp < 0.20 ? ghostOp : Math.max(ghostOp, matchMaterialize);
    const op = baseOp * matchQuiet;
    const scale = sp < 0.20 ? 0.94 : (0.94 + 0.06 * matchMaterialize) * (sp > 0.40 ? 0.98 : 1);
    const tx = sp < 0.20 ? 15 : 15 * (1 - matchMaterialize);
    const tz = sp < 0.20 ? 0 : 14 * matchMaterialize * (sp > 0.40 ? Math.max(0, 1 - (sp - 0.40) / 0.18) : 1);
    return {
      opacity: op,
      transform: `translate3d(${tx}px, 0px, ${tz}px) scale(${scale})`,
    };
  }, [sp, matchMaterialize, matchQuiet]);

  // ==========================================
  // PROCESS CARD 2: VERIFY
  // ==========================================
  const verifyMaterialize = Math.min(1, Math.max(0, (sp - 0.40) / 0.16));
  const verifyQuiet = sp > 0.58 ? Math.max(0.70, 1 - ((sp - 0.58) / 0.20) * 0.30) : 1;
  const verifyActive = sp >= 0.44 && sp < 0.62;
  const verifyStatusText = sp < 0.46 ? 'Checking...' : 'Variance detected';

  const verifyStyle = useMemo(() => {
    const ghostOp = 0.05;
    const baseOp = sp < 0.40 ? ghostOp : Math.max(ghostOp, verifyMaterialize);
    const op = baseOp * verifyQuiet;
    const scale = sp < 0.40 ? 0.94 : (0.96 + 0.04 * verifyMaterialize) * (sp > 0.58 ? 0.98 : 1);
    const tx = sp < 0.40 ? 20 : 20 * (1 - verifyMaterialize);
    const tz = sp < 0.40 ? -15 : (-15 + 30 * verifyMaterialize) * (sp > 0.58 ? Math.max(0, 1 - (sp - 0.58) / 0.16) : 1);
    return {
      opacity: op,
      transform: `translate3d(${tx}px, 0px, ${tz}px) scale(${scale})`,
    };
  }, [sp, verifyMaterialize, verifyQuiet]);

  // ==========================================
  // PROCESS CARD 3: CLASSIFY
  // ==========================================
  const classifyMaterialize = Math.min(1, Math.max(0, (sp - 0.58) / 0.15));
  const classifyQuiet = sp > 0.74 ? Math.max(0.70, 1 - ((sp - 0.74) / 0.20) * 0.30) : 1;
  const classifyActive = sp >= 0.62 && sp < 0.78;
  const classifyStatusText = sp < 0.64 ? 'Analysing...' : 'Exception identified';

  const classifyStyle = useMemo(() => {
    const ghostOp = 0.05;
    const baseOp = sp < 0.58 ? ghostOp : Math.max(ghostOp, classifyMaterialize);
    const op = baseOp * classifyQuiet;
    const scale = sp < 0.58 ? 0.94 : (0.96 + 0.04 * classifyMaterialize) * (sp > 0.74 ? 0.98 : 1);
    const tx = sp < 0.58 ? 20 : 20 * (1 - classifyMaterialize);
    const tz = sp < 0.58 ? -15 : (-15 + 30 * classifyMaterialize) * (sp > 0.74 ? Math.max(0, 1 - (sp - 0.74) / 0.16) : 1);
    return {
      opacity: op,
      transform: `translate3d(${tx}px, 0px, ${tz}px) scale(${scale})`,
    };
  }, [sp, classifyMaterialize, classifyQuiet]);

  // ==========================================
  // RESULT CARDS COMPUTED STYLES
  // ==========================================
  // AUTO VERIFIED: stays low opacity / neutral (~0.35)
  const autoVerifiedStyle = useMemo(() => {
    const ghostOp = 0.05;
    const op = sp < 0.74 ? ghostOp : ghostOp + 0.30 * s5_results;
    return {
      opacity: op,
      transform: 'translate3d(0px, 0px, -10px) scale(0.97)',
    };
  }, [sp, s5_results]);

  // REVIEW REQUIRED (The active selected outcome)
  // Reaches full 100% opacity, moves forward ~10-12px in Z-space, scale 1.01
  const reviewRequiredStyle = useMemo(() => {
    const ghostOp = 0.05;
    const op = sp < 0.74 ? ghostOp : ghostOp + 0.95 * s5_results;
    const tz = 12 * s5_results;
    const scale = 0.96 + 0.05 * s5_results;
    return {
      opacity: op,
      transform: `translate3d(0px, 0px, ${tz}px) scale(${scale})`,
    };
  }, [sp, s5_results]);

  // UNRESOLVED: stays low opacity / neutral (~0.35)
  const unresolvedStyle = useMemo(() => {
    const ghostOp = 0.05;
    const op = sp < 0.74 ? ghostOp : ghostOp + 0.30 * s5_results;
    return {
      opacity: op,
      transform: 'translate3d(0px, 0px, -10px) scale(0.97)',
    };
  }, [sp, s5_results]);

  // ==========================================
  // SVG RAIL DRAWING PROGRESS (strokeDashoffset)
  // ==========================================
  // Intake rails draw: 0.12 -> 0.20
  const intakeDraw = Math.min(100, Math.max(0, ((sp - 0.10) / 0.10) * 100));

  // Spine MATCH -> VERIFY draws: 0.38 -> 0.44
  const spine1Draw = Math.min(100, Math.max(0, ((sp - 0.38) / 0.06) * 100));

  // Spine VERIFY -> CLASSIFY draws: 0.56 -> 0.62
  const spine2Draw = Math.min(100, Math.max(0, ((sp - 0.56) / 0.06) * 100));

  // Output rails draw: 0.72 -> 0.84
  const outputDraw = Math.min(100, Math.max(0, ((sp - 0.72) / 0.12) * 100));

  // ==========================================
  // SINGLE MOVING PULSE PER ACTIVE STAGE
  // ==========================================
  // Stage 1 & 2 intake pulses (from 260 to 340):
  let intakePulseP = 0;
  let showIntakePulses = false;
  if (sp >= 0.12 && sp < 0.24) {
    showIntakePulses = true;
    intakePulseP = (sp - 0.12) / 0.12;
  }

  // Stage 3 packet MATCH -> VERIFY (440 to 450):
  let packet3X = 440;
  let showPacket3 = false;
  if (sp >= 0.38 && sp < 0.46) {
    showPacket3 = true;
    const p = (sp - 0.38) / 0.08;
    packet3X = 438 + p * 14;
  }

  // Stage 4 packet VERIFY -> CLASSIFY (550 to 560):
  let packet4X = 550;
  let showPacket4 = false;
  if (sp >= 0.56 && sp < 0.64) {
    showPacket4 = true;
    const p = (sp - 0.56) / 0.08;
    packet4X = 548 + p * 14;
  }

  // Stage 5 packet CLASSIFY -> REVIEW REQUIRED (660 to 730):
  let packet5X = 660;
  let showPacket5 = false;
  if (sp >= 0.74 && sp < 0.88) {
    showPacket5 = true;
    const p = (sp - 0.74) / 0.14;
    packet5X = 660 + p * 70;
  }

  return (
    <section
      id="architecture"
      ref={containerRef}
      className="relative w-full h-[240vh] bg-[#050B14]"
    >
      {/* Sticky Cockpit Canvas: Pinned smoothly while user scrolls through 240vh */}
      <div className="sticky top-0 h-screen w-full flex flex-col justify-center items-center py-6 px-4 sm:px-8 max-w-6xl mx-auto overflow-hidden z-20">
        
        {/* Section Header: Minimal & Restrained */}
        <div className="text-center max-w-lg mx-auto mb-5 flex-shrink-0">
          <div className="inline-flex items-center gap-2 text-[11px] font-mono tracking-widest text-[#91A0B6] uppercase mb-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#22D3EE]" />
            RECONCILIATION ENGINE
          </div>
          <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[#F4F7FB] leading-tight mb-1.5">
            One engine. Three outcomes.
          </h2>
          <p className="text-xs sm:text-sm text-[#91A0B6] font-normal leading-relaxed">
            Multi-source intake resolves deterministically into financial truth.
          </p>

          {/* Thin Hairline Progress Indicator */}
          <div className="mt-2.5 w-36 h-[2px] bg-[#1A263D] mx-auto rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-[#22D3EE] via-[#818CF8] to-[#F59E0B] transition-all duration-75 ease-out"
              style={{ width: `${Math.round(sp * 100)}%` }}
            />
          </div>
        </div>

        {/* ==================================================================== */}
        {/* DESKTOP SPATIAL CARD SEQUENCE CANVAS (>= 900px) */}
        {/* ==================================================================== */}
        <div
          className="hidden md:flex w-full max-w-5xl h-[420px] relative rounded-2xl bg-[#09111E]/95 border border-[#1A263D]/80 p-6 backdrop-blur-xl shadow-[0_24px_60px_rgba(0,0,0,0.5)] items-center justify-between overflow-hidden"
          style={{
            perspective: '1200px',
            transform: `rotateX(${mousePos.y * -0.8}deg) rotateY(${mousePos.x * 0.8}deg)`,
            transition: 'transform 0.15s ease-out',
          }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          {/* Connecting Animated Financial Rails (SVG overlay: 1000 x 420) */}
          <svg
            viewBox="0 0 1000 420"
            className="absolute inset-0 w-full h-full pointer-events-none"
            fill="none"
          >
            {/* INTAKE RAILS: 3 Sources to MATCH (340, 210) */}
            {/* Background inactive tracks */}
            <path
              d="M 260 70 C 300 70, 305 210, 340 210"
              stroke={hoveredNode === 'invoices' ? 'rgba(34, 211, 238, 0.4)' : 'rgba(148, 163, 184, 0.12)'}
              strokeWidth="1.2"
            />
            <path
              d="M 260 210 L 340 210"
              stroke={hoveredNode === 'settlements' ? 'rgba(34, 211, 238, 0.4)' : 'rgba(148, 163, 184, 0.12)'}
              strokeWidth="1.2"
            />
            <path
              d="M 260 350 C 300 350, 305 210, 340 210"
              stroke={hoveredNode === 'bank' ? 'rgba(34, 211, 238, 0.4)' : 'rgba(148, 163, 184, 0.12)'}
              strokeWidth="1.2"
            />

            {/* Dynamically drawn active intake rails */}
            {intakeDraw > 0 && (
              <>
                <path
                  d="M 260 70 C 300 70, 305 210, 340 210"
                  stroke="rgba(34, 211, 238, 0.75)"
                  strokeWidth="1.2"
                  pathLength={100}
                  strokeDasharray="100"
                  strokeDashoffset={100 - intakeDraw}
                />
                <path
                  d="M 260 210 L 340 210"
                  stroke="rgba(34, 211, 238, 0.75)"
                  strokeWidth="1.2"
                  pathLength={100}
                  strokeDasharray="100"
                  strokeDashoffset={100 - intakeDraw}
                />
                <path
                  d="M 260 350 C 300 350, 305 210, 340 210"
                  stroke="rgba(34, 211, 238, 0.75)"
                  strokeWidth="1.2"
                  pathLength={100}
                  strokeDasharray="100"
                  strokeDashoffset={100 - intakeDraw}
                />
              </>
            )}

            {/* Moving pulses from sources */}
            {showIntakePulses && (
              <>
                <circle
                  cx={260 + intakePulseP * 80}
                  cy={70 + intakePulseP * 140}
                  r="2.5"
                  fill="#22D3EE"
                />
                <circle
                  cx={260 + intakePulseP * 80}
                  cy={210}
                  r="2.5"
                  fill="#22D3EE"
                />
                <circle
                  cx={260 + intakePulseP * 80}
                  cy={350 - intakePulseP * 140}
                  r="2.5"
                  fill="#22D3EE"
                />
              </>
            )}

            {/* PROCESS CONNECTOR 1: MATCH (440) -> VERIFY (450) */}
            <path
              d="M 440 210 L 450 210"
              stroke={hoveredNode === 'match' || hoveredNode === 'verify' ? 'rgba(129, 140, 248, 0.6)' : 'rgba(148, 163, 184, 0.14)'}
              strokeWidth="1.5"
            />
            {spine1Draw > 0 && (
              <path
                d="M 440 210 L 450 210"
                stroke="rgba(129, 140, 248, 0.85)"
                strokeWidth="1.5"
                pathLength={100}
                strokeDasharray="100"
                strokeDashoffset={100 - spine1Draw}
              />
            )}
            {showPacket3 && (
              <circle cx={packet3X} cy={210} r="2.5" fill="#818CF8" />
            )}

            {/* PROCESS CONNECTOR 2: VERIFY (550) -> CLASSIFY (560) */}
            <path
              d="M 550 210 L 560 210"
              stroke={hoveredNode === 'verify' || hoveredNode === 'classify' ? 'rgba(245, 158, 11, 0.6)' : 'rgba(148, 163, 184, 0.14)'}
              strokeWidth="1.5"
            />
            {spine2Draw > 0 && (
              <path
                d="M 550 210 L 560 210"
                stroke="rgba(245, 158, 11, 0.85)"
                strokeWidth="1.5"
                pathLength={100}
                strokeDasharray="100"
                strokeDashoffset={100 - spine2Draw}
              />
            )}
            {showPacket4 && (
              <circle cx={packet4X} cy={210} r="2.5" fill="#F59E0B" />
            )}

            {/* OUTPUT RAILS: CLASSIFY (660, 210) -> 3 Outcomes (730) */}
            {/* Background inactive tracks */}
            <path
              d="M 660 210 C 695 210, 700 70, 730 70"
              stroke={hoveredNode === 'auto_verified' ? 'rgba(45, 212, 167, 0.4)' : 'rgba(148, 163, 184, 0.12)'}
              strokeWidth="1.2"
            />
            <path
              d="M 660 210 L 730 210"
              stroke={hoveredNode === 'review_required' ? 'rgba(245, 158, 11, 0.6)' : 'rgba(148, 163, 184, 0.14)'}
              strokeWidth="1.2"
            />
            <path
              d="M 660 210 C 695 210, 700 350, 730 350"
              stroke={hoveredNode === 'unresolved' ? 'rgba(239, 91, 103, 0.4)' : 'rgba(148, 163, 184, 0.12)'}
              strokeWidth="1.2"
            />

            {/* Dynamically drawn active output rails */}
            {outputDraw > 0 && (
              <>
                <path
                  d="M 660 210 C 695 210, 700 70, 730 70"
                  stroke="rgba(45, 212, 167, 0.4)"
                  strokeWidth="1.2"
                  pathLength={100}
                  strokeDasharray="100"
                  strokeDashoffset={100 - outputDraw}
                />
                <path
                  d="M 660 210 L 730 210"
                  stroke="rgba(245, 158, 11, 0.9)"
                  strokeWidth="1.5"
                  pathLength={100}
                  strokeDasharray="100"
                  strokeDashoffset={100 - outputDraw}
                />
                <path
                  d="M 660 210 C 695 210, 700 350, 730 350"
                  stroke="rgba(239, 91, 103, 0.4)"
                  strokeWidth="1.2"
                  pathLength={100}
                  strokeDasharray="100"
                  strokeDashoffset={100 - outputDraw}
                />
              </>
            )}

            {/* Active packet traveling into REVIEW REQUIRED */}
            {showPacket5 && (
              <circle cx={packet5X} cy={210} r="3" fill="#F59E0B" />
            )}
          </svg>

          {/* ------------------------------------------------------------- */}
          {/* COLUMN 1: 3 INPUT CARDS (~26% width) */}
          {/* ------------------------------------------------------------- */}
          <div className="w-[26%] h-full flex flex-col justify-between py-1 relative z-10">
            
            {/* Card 1: INVOICES */}
            <div
              onMouseEnter={() => setHoveredNode('invoices')}
              onMouseLeave={() => setHoveredNode(null)}
              style={invStyle}
              className={`p-3.5 rounded-2xl bg-[#0B1524] border transition-colors duration-200 cursor-default ${
                hoveredNode === 'invoices' ? 'border-[#22D3EE]/50 shadow-sm' : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="font-medium text-[#F4F7FB] tracking-wide">INVOICES</span>
                <span className="text-[10px] text-[#22D3EE]/90">AR/4115</span>
              </div>
              <div className="text-[11px] font-mono text-[#91A0B6] mt-1">
                ₹9,18,000 · ERP
              </div>
            </div>

            {/* Card 2: SETTLEMENTS */}
            <div
              onMouseEnter={() => setHoveredNode('settlements')}
              onMouseLeave={() => setHoveredNode(null)}
              style={setStyle}
              className={`p-3.5 rounded-2xl bg-[#0B1524] border transition-colors duration-200 cursor-default ${
                hoveredNode === 'settlements' ? 'border-[#22D3EE]/50 shadow-sm' : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="font-medium text-[#F4F7FB] tracking-wide">SETTLEMENTS</span>
                <span className="text-[10px] text-[#22D3EE]/90">SET-88421</span>
              </div>
              <div className="text-[11px] font-mono text-[#91A0B6] mt-1">
                ₹8,74,500 · Gateway
              </div>
            </div>

            {/* Card 3: BANK */}
            <div
              onMouseEnter={() => setHoveredNode('bank')}
              onMouseLeave={() => setHoveredNode(null)}
              style={bnkStyle}
              className={`p-3.5 rounded-2xl bg-[#0B1524] border transition-colors duration-200 cursor-default ${
                hoveredNode === 'bank' ? 'border-[#22D3EE]/50 shadow-sm' : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="font-medium text-[#F4F7FB] tracking-wide">BANK</span>
                <span className="text-[10px] text-[#22D3EE]/90">UTR-629183</span>
              </div>
              <div className="text-[11px] font-mono text-[#91A0B6] mt-1">
                ₹8,74,500 · Direct
              </div>
            </div>

          </div>

          {/* ------------------------------------------------------------- */}
          {/* COLUMN 2: 3 PROCESS CARDS (~45% width) */}
          {/* ------------------------------------------------------------- */}
          <div className="w-[45%] flex items-center justify-center gap-2.5 relative z-10 px-2">
            
            {/* PROCESS 01: MATCH */}
            <div
              onMouseEnter={() => setHoveredNode('match')}
              onMouseLeave={() => setHoveredNode(null)}
              style={matchStyle}
              className={`flex-1 min-h-[105px] p-3 rounded-2xl bg-[#0B1524] border text-center flex flex-col justify-between transition-colors duration-200 cursor-default ${
                matchActive
                  ? 'border-[#22D3EE]/60 shadow-[0_4px_20px_rgba(34,211,238,0.12)]'
                  : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="text-[10px] font-mono text-[#91A0B6]/80 font-medium">01</div>
              <div>
                <div className="text-xs font-mono font-semibold tracking-wider text-[#F4F7FB]">
                  MATCH
                </div>
                <div className={`text-[10px] font-mono mt-1 ${matchActive ? 'text-[#22D3EE]' : 'text-[#91A0B6]/60'}`}>
                  {matchStatusText}
                </div>
              </div>
              <div className="h-1" />
            </div>

            {/* PROCESS 02: VERIFY */}
            <div
              onMouseEnter={() => setHoveredNode('verify')}
              onMouseLeave={() => setHoveredNode(null)}
              style={verifyStyle}
              className={`flex-1 min-h-[105px] p-3 rounded-2xl bg-[#0B1524] border text-center flex flex-col justify-between transition-colors duration-200 cursor-default ${
                verifyActive
                  ? 'border-[#818CF8]/70 shadow-[0_4px_20px_rgba(129,140,248,0.14)]'
                  : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="text-[10px] font-mono text-[#91A0B6]/80 font-medium">02</div>
              <div>
                <div className="text-xs font-mono font-semibold tracking-wider text-[#F4F7FB]">
                  VERIFY
                </div>
                {/* Evidence comparison appears during verify active stage */}
                {sp >= 0.42 && (
                  <div className="my-1 py-0.5 px-1 bg-[#060D17] rounded border border-[#1E293B] text-[9px] font-mono text-[#91A0B6] flex flex-col items-center">
                    <span className="text-[8.5px] leading-tight text-[#CBD5E1]">₹9.18L vs ₹8.74L</span>
                    <span className="text-[#818CF8] text-[8.5px] font-medium leading-tight">Δ ₹43,500</span>
                  </div>
                )}
                <div className={`text-[10px] font-mono ${verifyActive ? 'text-[#818CF8]' : 'text-[#91A0B6]/60'}`}>
                  {verifyStatusText}
                </div>
              </div>
              <div className="h-0.5" />
            </div>

            {/* PROCESS 03: CLASSIFY */}
            <div
              onMouseEnter={() => setHoveredNode('classify')}
              onMouseLeave={() => setHoveredNode(null)}
              style={classifyStyle}
              className={`flex-1 min-h-[105px] p-3 rounded-2xl bg-[#0B1524] border text-center flex flex-col justify-between transition-colors duration-200 cursor-default ${
                classifyActive
                  ? 'border-[#F59E0B]/70 shadow-[0_4px_20px_rgba(245,158,11,0.14)]'
                  : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="text-[10px] font-mono text-[#91A0B6]/80 font-medium">03</div>
              <div>
                <div className="text-xs font-mono font-semibold tracking-wider text-[#F4F7FB]">
                  CLASSIFY
                </div>
                {sp >= 0.63 && (
                  <div className="my-1 inline-block px-1.5 py-0.5 rounded bg-[#F59E0B]/10 border border-[#F59E0B]/30 text-[9px] font-mono text-[#F59E0B] font-medium">
                    MDR VARIANCE
                  </div>
                )}
                <div className={`text-[10px] font-mono ${classifyActive ? 'text-[#F59E0B]' : 'text-[#91A0B6]/60'}`}>
                  {classifyStatusText}
                </div>
              </div>
              <div className="h-0.5" />
            </div>

          </div>

          {/* ------------------------------------------------------------- */}
          {/* COLUMN 3: 3 RESULT CARDS (~29% width) */}
          {/* ------------------------------------------------------------- */}
          <div className="w-[29%] h-full flex flex-col justify-between py-1 relative z-10">
            
            {/* Result 1: AUTO VERIFIED (Neutral / Low Opacity) */}
            <div
              onMouseEnter={() => setHoveredNode('auto_verified')}
              onMouseLeave={() => setHoveredNode(null)}
              style={autoVerifiedStyle}
              className={`p-3.5 rounded-2xl bg-[#0B1524] border transition-colors duration-200 cursor-default ${
                hoveredNode === 'auto_verified' ? 'border-[#2DD4A7]/40' : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="flex items-center gap-1.5 text-xs font-mono font-medium text-[#91A0B6]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#2DD4A7]/60" />
                <span>AUTO VERIFIED</span>
              </div>
              <div className="text-[10.5px] font-mono text-[#91A0B6]/70 mt-1">
                Cleared to GL · Zero touch
              </div>
            </div>

            {/* Result 2: REVIEW REQUIRED (Active Selected Outcome) */}
            <div
              onMouseEnter={() => setHoveredNode('review_required')}
              onMouseLeave={() => setHoveredNode(null)}
              style={reviewRequiredStyle}
              className={`p-3.5 rounded-2xl bg-[#0D1829] border transition-all duration-200 cursor-default ${
                sp >= 0.74
                  ? 'border-[#F59E0B]/60 shadow-[0_8px_24px_rgba(245,158,11,0.16)]'
                  : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-xs font-mono font-semibold text-[#F59E0B]">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B] animate-pulse" />
                  <span>REVIEW REQUIRED</span>
                </div>
                <span className="text-[10px] font-mono text-[#EF4444] font-medium">−₹43,500</span>
              </div>
              <div className="text-[11px] font-mono text-[#F4F7FB] mt-1 font-medium">
                MDR variance isolated
              </div>
              <div className="text-[10px] font-mono text-[#91A0B6] mt-0.5">
                Human check needed
              </div>
            </div>

            {/* Result 3: UNRESOLVED (Neutral / Low Opacity) */}
            <div
              onMouseEnter={() => setHoveredNode('unresolved')}
              onMouseLeave={() => setHoveredNode(null)}
              style={unresolvedStyle}
              className={`p-3.5 rounded-2xl bg-[#0B1524] border transition-colors duration-200 cursor-default ${
                hoveredNode === 'unresolved' ? 'border-[#EF5B67]/40' : 'border-[#94A3B8]/15'
              }`}
            >
              <div className="flex items-center gap-1.5 text-xs font-mono font-medium text-[#91A0B6]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#EF5B67]/60" />
                <span>UNRESOLVED</span>
              </div>
              <div className="text-[10.5px] font-mono text-[#91A0B6]/70 mt-1">
                Missing gateway feed
              </div>
            </div>

          </div>

        </div>

        {/* ==================================================================== */}
        {/* MOBILE RESPONSIVE ADAPTATION (< 900px) */}
        {/* Clean, vertical scroll-activated card progression */}
        {/* ==================================================================== */}
        <div className="flex md:hidden w-full max-w-sm flex-col gap-3 py-2 px-3 rounded-2xl bg-[#09111E]/95 border border-[#1A263D]/80">
          {/* Source Group */}
          <div
            className="p-3 rounded-xl bg-[#0B1524] border border-[#94A3B8]/15 transition-opacity duration-300"
            style={{ opacity: Math.max(0.4, s1_inv) }}
          >
            <div className="text-[10px] font-mono text-[#22D3EE] uppercase tracking-wider mb-1">
              3 Financial Records Ingested
            </div>
            <div className="text-xs font-mono text-[#F4F7FB]">
              Invoice AR/4115 · Settlement SET-88421 · Bank UTR-629183
            </div>
          </div>

          <div className="w-px h-3 bg-[#1A263D] mx-auto" />

          {/* Process Sequence */}
          <div className="grid grid-cols-3 gap-2">
            <div
              className={`p-2 rounded-xl border text-center transition-all duration-300 ${
                matchActive ? 'bg-[#0E1A2B] border-[#22D3EE]/60 text-[#22D3EE]' : 'bg-[#0B1524] border-[#94A3B8]/15 text-[#91A0B6]/70'
              }`}
            >
              <div className="text-[9px] font-mono">01 MATCH</div>
              <div className="text-[10px] font-mono font-semibold mt-0.5">{matchStatusText}</div>
            </div>

            <div
              className={`p-2 rounded-xl border text-center transition-all duration-300 ${
                verifyActive ? 'bg-[#0E1A2B] border-[#818CF8]/70 text-[#818CF8]' : 'bg-[#0B1524] border-[#94A3B8]/15 text-[#91A0B6]/70'
              }`}
            >
              <div className="text-[9px] font-mono">02 VERIFY</div>
              <div className="text-[10px] font-mono font-semibold mt-0.5">{verifyStatusText}</div>
            </div>

            <div
              className={`p-2 rounded-xl border text-center transition-all duration-300 ${
                classifyActive ? 'bg-[#0E1A2B] border-[#F59E0B]/70 text-[#F59E0B]' : 'bg-[#0B1524] border-[#94A3B8]/15 text-[#91A0B6]/70'
              }`}
            >
              <div className="text-[9px] font-mono">03 CLASSIFY</div>
              <div className="text-[10px] font-mono font-semibold mt-0.5">{classifyStatusText}</div>
            </div>
          </div>

          <div className="w-px h-3 bg-[#1A263D] mx-auto" />

          {/* Result Card: Review Required */}
          <div
            className={`p-3 rounded-xl border transition-all duration-300 ${
              sp >= 0.74 ? 'bg-[#0D1829] border-[#F59E0B]/70 text-[#F4F7FB]' : 'bg-[#0B1524] border-[#94A3B8]/15 text-[#91A0B6]/50'
            }`}
          >
            <div className="flex items-center justify-between text-xs font-mono font-semibold">
              <span className="text-[#F59E0B]">REVIEW REQUIRED</span>
              <span className="text-[#EF4444]">−₹43,500</span>
            </div>
            <div className="text-[11px] font-mono text-[#CBD5E1] mt-1">
              MDR variance isolated · Human check needed
            </div>
          </div>
        </div>

        {/* ==================================================================== */}
        {/* Subdued Final Status Line */}
        {/* ==================================================================== */}
        <div className="text-center text-xs font-mono text-[#91A0B6]/70 flex-shrink-0 flex items-center justify-center gap-2 mt-4 tracking-wide">
          <span className="w-1.5 h-1.5 rounded-full bg-[#22D3EE]/80" />
          <span>Evidence in. Decision out.</span>
        </div>

      </div>
    </section>
  );
};
