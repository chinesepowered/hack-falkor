/**
 * Capy: the CapyBrain mascot.
 *
 * A calm capybara (facing right) with a yuzu balanced on its head. With `bath`,
 * Capy soaks in a teal hot spring. Pure inline SVG, no external assets.
 *
 * `size` is the rendered width in px; the height is `size * 0.8` (art is 1.25:1).
 *
 * Animation hooks (keyframes live in src/styles/capy-animations.css):
 *   .capy-yuzu    the yuzu (gentle bob)
 *   .capy-blink   the eye (periodic blink)
 *   .capy-dots    the three thinking dots (pulse in sequence)
 *   .capy-ripple  ripple arcs on the water (expand and fade)
 *   .capy-steam   steam wisps (drift up and fade)
 */

export type CapyMood = 'idle' | 'thinking' | 'alert' | 'happy';

const COLOR = {
  body: '#A8744A',
  shade: '#8A5C37',
  snout: '#6B4528',
  earInner: '#7A4F2E',
  eye: '#2B1D14',
  eyeWhite: '#FFF6EA',
  blush: '#F2A7A0',
  tongue: '#E98A8A',
  yuzu: '#F5B635',
  yuzuShade: '#E9A425',
  yuzuHi: '#FFD877',
  leaf: '#6BAA4A',
  leafVein: '#4E8A35',
  water: '#2A9D8F',
  waterHi: '#57C1B3',
  steam: 'rgba(255,255,255,0.7)',
  sweat: '#8ACFEA',
  bubbleLine: '#E6D9C8',
  white: '#FFFFFF',
} as const;

const LABEL: Record<CapyMood, string> = {
  idle: 'Capy the capybara',
  thinking: 'Capy the capybara, thinking',
  alert: 'Capy the capybara, noticing something',
  happy: 'Capy the capybara, happy',
};

/* ------------------------------------------------------------------ geometry */

const r2 = (n: number) => Math.round(n * 100) / 100;

const BODY =
  'M116 60C96 49 64 48 47 58C31 68 28 92 31 111C34 131 56 142 86 142C114 142 138 138 148 126C156 116 154 98 140 86Z';
/** Same body, cut off flat below the waterline (only used in the bath). */
const BODY_BATH = 'M116 60C96 49 64 48 47 58C31 68 28 92 31 111L34 124L150 124C155 112 152 98 140 86Z';
const BELLY =
  'M34 120C42 134 60 142 86 142C114 142 138 138 148 126C134 134 112 136 88 136C64 136 46 130 34 120Z';
const CHEST_SHADOW =
  'M108 94C116 104 130 109 144 109C148 109 151 108.5 153.5 107.5C154 104 153.5 100 152 97C140 101 122 100 108 94Z';
const HEAD =
  'M102 76C99 56 110 38 132 35C150 32.5 168 35 179 41C186 45 189 52 189 60L189 84C189 96 182 103 170 103.5C158 104 140 106 128 105C112 104 102 94 102 76Z';
const EAR = 'M106.5 45C103.5 37 106.5 29.5 113 29C119.5 28.5 123.5 34.5 122 42Z';
const EAR_INNER = 'M109.5 42.5C108 37.5 109.8 32.8 113.5 32.6C117.2 32.4 119.6 36.2 118.8 40.8Z';
const NOSE = 'M174 41.2C182.5 42.5 189.5 49 190 58L190 63C185.5 64.5 180.5 62 178 57.5C176 53.5 174.8 47.5 174 41.2Z';

const EYE = { x: 148, y: 59 };

/** How far Capy sinks into the water in bath mode. */
const SINK = 6;

// Hot-spring pool: an ellipse seen from slightly above.
const POOL = { cx: 100, cy: 128, rx: 95, ry: 24 };
const WATER_Y = 108 + SINK;

function poolHalfWidthAt(y: number) {
  const t = (y - POOL.cy) / POOL.ry;
  return POOL.rx * Math.sqrt(1 - t * t);
}

/** A gently wavy horizontal line from x0 to x1 (path data without the leading M). */
function wave(x0: number, x1: number, y: number, amp: number, segments: number) {
  const w = (x1 - x0) / segments;
  let d = '';
  for (let i = 0; i < segments; i++) {
    const cx = x0 + w * (i + 0.5);
    const cy = y + (i % 2 === 0 ? -amp : amp);
    d += `Q${r2(cx)} ${r2(cy)} ${r2(x0 + w * (i + 1))} ${r2(y)}`;
  }
  return d;
}

const WATER_HALF = poolHalfWidthAt(WATER_Y);
const WATER_X0 = r2(POOL.cx - WATER_HALF);
const WATER_X1 = r2(POOL.cx + WATER_HALF);
const WAVE_SEGMENTS = 8;
const FRONT_WATER = `M${WATER_X0} ${WATER_Y}${wave(WATER_X0, WATER_X1, WATER_Y, 2.2, WAVE_SEGMENTS)}A${POOL.rx} ${POOL.ry} 0 1 1 ${WATER_X0} ${WATER_Y}Z`;

// The bright line where the water meets Capy's fur (same wave, only across the body).
const SEG_W = (WATER_X1 - WATER_X0) / WAVE_SEGMENTS;
const SHORE_X0 = r2(WATER_X0 + SEG_W);
const SHORE_X1 = r2(WATER_X0 + SEG_W * 7);
const WATERLINE = `M${SHORE_X0} ${WATER_Y}${wave(SHORE_X0, SHORE_X1, WATER_Y, -2.2, 6)}`;

/** Lower (front) half of an ellipse centred on the waterline. */
const rippleArc = (cx: number, rx: number, ry: number) =>
  `M${cx - rx} ${WATER_Y}A${rx} ${ry} 0 0 0 ${cx + rx} ${WATER_Y}`;

// Sized so that even at the animation's 1.3x scale they stay (nearly) inside the pool.
const RIPPLES = [
  { d: rippleArc(96, 40, 9), opacity: 0.9 },
  { d: rippleArc(96, 52, 12), opacity: 0.6 },
  { d: rippleArc(96, 64, 15), opacity: 0.35 },
];

/** A soft steam wisp: one gentle S-curve of height h rising from (x, y). */
const wisp = (x: number, y: number, h: number, a: number) => `M${x} ${y}q${-a} ${-h / 4} 0 ${-h / 2}t0 ${-h / 2}`;

const STEAM = [wisp(18, 104, 30, 8), wisp(50, 58, 44, 10), wisp(76, 52, 36, 10)];

/* ------------------------------------------------------------------ parts */

function Eye({ mood }: { mood: CapyMood }) {
  const { x, y } = EYE;
  if (mood === 'happy') {
    return (
      <path
        d={`M${x - 6.5} ${y + 2.5}Q${x} ${y - 5.5} ${x + 6.5} ${y + 2.5}`}
        fill="none"
        stroke={COLOR.eye}
        strokeWidth={3.2}
        strokeLinecap="round"
      />
    );
  }
  if (mood === 'alert') {
    return (
      <g className="capy-blink">
        <circle cx={x} cy={y} r={6.6} fill={COLOR.eye} />
        <circle cx={x + 2.3} cy={y - 2.4} r={2.2} fill={COLOR.white} />
        <circle cx={x - 2.4} cy={y + 2.7} r={0.95} fill={COLOR.white} />
      </g>
    );
  }
  if (mood === 'thinking') {
    // Pupil rolled up (a sliver of eye-white shows underneath) and a raised brow.
    return (
      <g>
        <path
          d={`M${x - 5} ${y - 11.5}Q${x + 1} ${y - 14.5} ${x + 7} ${y - 11}`}
          fill="none"
          stroke={COLOR.snout}
          strokeWidth={2}
          strokeLinecap="round"
        />
        <g className="capy-blink">
          <ellipse cx={x} cy={y} rx={6.6} ry={7} fill={COLOR.eyeWhite} />
          <circle cx={x + 0.6} cy={y - 1.6} r={5.4} fill={COLOR.eye} />
          <circle cx={x + 2.2} cy={y - 3.8} r={1.6} fill={COLOR.white} />
        </g>
      </g>
    );
  }
  // idle: calm, half-lidded
  return (
    <g className="capy-blink">
      <path
        d={`M${x - 6.8} ${y - 0.5}C${x - 6.8} ${y + 8.5} ${x + 6.8} ${y + 8.5} ${x + 6.8} ${y - 0.5}C${x + 3} ${y - 2.2} ${x - 3} ${y - 2.2} ${x - 6.8} ${y - 0.5}Z`}
        fill={COLOR.eye}
      />
      <circle cx={x + 2.5} cy={y + 2} r={1.5} fill={COLOR.white} />
    </g>
  );
}

function Mouth({ mood }: { mood: CapyMood }) {
  const line = {
    fill: 'none',
    stroke: COLOR.snout,
    strokeWidth: 2.2,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
  };
  if (mood === 'alert') {
    return (
      <>
        <path d="M184.5 66.5V70" {...line} />
        <ellipse cx={182} cy={74.6} rx={2.4} ry={2.9} fill={COLOR.snout} />
      </>
    );
  }
  if (mood === 'thinking') {
    return <path d="M184.5 66.5V71M178.5 73.4L184.5 72.4" {...line} />;
  }
  if (mood === 'happy') {
    return (
      <>
        <path d="M184.5 66.5V70" {...line} />
        <path d="M177 70.2Q181.5 80 186.5 70.2Z" fill={COLOR.snout} stroke={COLOR.snout} strokeWidth={1.6} strokeLinejoin="round" />
        <path d="M179.4 74.6Q181.6 72.4 184 74.6Q181.8 76.6 179.4 74.6Z" fill={COLOR.tongue} />
      </>
    );
  }
  // a small, content "w" under the nose
  return <path d="M184.5 66.5V71M177 70.5Q179 75 182 73Q184.5 71 184.5 71Q184.5 71 187 73" {...line} />;
}

function MoodExtras({ mood }: { mood: CapyMood }) {
  if (mood === 'thinking') {
    return (
      <g>
        <g fill={COLOR.white} stroke={COLOR.bubbleLine} strokeWidth={1.2}>
          <circle cx={168} cy={34} r={2.2} />
          <circle cx={173.5} cy={28} r={3} />
          <rect x={160} y={4} width={38} height={20} rx={10} />
        </g>
        <g className="capy-dots" fill={COLOR.shade}>
          <circle cx={169} cy={14} r={3} />
          <circle cx={179} cy={14} r={3} />
          <circle cx={189} cy={14} r={3} />
        </g>
      </g>
    );
  }
  if (mood === 'alert') {
    return (
      <g>
        <path
          d="M95 22C91.5 28 89 32 89 35.5C89 39 91.7 41.5 95 41.5C98.3 41.5 101 39 101 35.5C101 32 98.5 28 95 22Z"
          fill={COLOR.sweat}
        />
        <ellipse cx={93} cy={36} rx={1.4} ry={2.2} fill={COLOR.white} />
      </g>
    );
  }
  if (mood === 'happy') {
    return (
      <g>
        <path d="M176 2Q177.4 10.6 186 12Q177.4 13.4 176 22Q174.6 13.4 166 12Q174.6 10.6 176 2Z" fill={COLOR.yuzu} />
        <path d="M191 26Q191.6 30.4 196 31Q191.6 31.6 191 36Q190.4 31.6 186 31Q190.4 30.4 191 26Z" fill={COLOR.yuzuHi} />
      </g>
    );
  }
  return null;
}

function Yuzu() {
  return (
    <g className="capy-yuzu">
      <path d="M145 11C145 8 146.3 5.8 148.6 4.6" fill="none" stroke={COLOR.snout} strokeWidth={2} strokeLinecap="round" />
      <path d="M146 9.5C140 4.5 131 4 126.5 7C131 12 140 13 146 9.5Z" fill={COLOR.leaf} />
      <path d="M145 9.4C139.5 7.2 133.5 6.6 128.5 7.2" fill="none" stroke={COLOR.leafVein} strokeWidth={1} strokeLinecap="round" />
      <ellipse cx={145} cy={23.5} rx={15} ry={13.5} fill={COLOR.yuzuShade} />
      <ellipse cx={144} cy={22.5} rx={13.8} ry={12.4} fill={COLOR.yuzu} />
      <ellipse cx={139.5} cy={18} rx={4.8} ry={3.3} fill={COLOR.yuzuHi} transform="rotate(-28 139.5 18)" />
      <g fill={COLOR.yuzuShade}>
        <circle cx={151} cy={27} r={0.9} />
        <circle cx={147} cy={31} r={0.8} />
        <circle cx={154} cy={21} r={0.8} />
      </g>
    </g>
  );
}

/* ------------------------------------------------------------------ component */

export default function Capy({
  mood = 'idle',
  size = 64,
  bath = false,
  className,
}: {
  mood?: CapyMood;
  size?: number;
  bath?: boolean;
  className?: string;
}) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 200 160"
      width={size}
      height={size * 0.8}
      className={className ? `capy ${className}` : 'capy'}
      role="img"
      aria-label={bath ? `${LABEL[mood]}, soaking in a hot spring` : LABEL[mood]}
    >
      {bath && (
        <g>
          <ellipse cx={POOL.cx} cy={POOL.cy - 1} rx={POOL.rx + 3.5} ry={POOL.ry + 3} fill={COLOR.waterHi} />
          <ellipse cx={POOL.cx} cy={POOL.cy} rx={POOL.rx} ry={POOL.ry} fill={COLOR.water} />
        </g>
      )}

      <g transform={bath ? `translate(0 ${SINK})` : undefined}>
        {!bath && (
          <g>
            <ellipse cx={94} cy={146.5} rx={62} ry={5} fill={COLOR.eye} fillOpacity={0.12} />
            <rect x={58} y={128} width={15} height={16.5} rx={6.5} fill={COLOR.shade} />
            <rect x={128} y={126} width={15} height={18.5} rx={6.5} fill={COLOR.shade} />
          </g>
        )}

        {/* body */}
        <path d={bath ? BODY_BATH : BODY} fill={COLOR.body} />
        {!bath && (
          <g>
            <path d={BELLY} fill={COLOR.shade} />
            <path d="M46 96C52 112 64 120 78 122" fill="none" stroke={COLOR.shade} strokeWidth={3} strokeLinecap="round" strokeOpacity={0.55} />
            <g fill={COLOR.body}>
              <rect x={42} y={126} width={18} height={20} rx={8} />
              <rect x={110} y={127} width={18} height={19} rx={8} />
            </g>
          </g>
        )}

        {/* head */}
        <path d={CHEST_SHADOW} fill={COLOR.shade} />
        <path d={EAR} fill={COLOR.body} />
        <path d={EAR_INNER} fill={COLOR.earInner} />
        <path d={HEAD} fill={COLOR.body} />
        <ellipse cx={145.5} cy={35.5} rx={11} ry={2.6} fill={COLOR.shade} fillOpacity={0.55} />
        <path d={NOSE} fill={COLOR.snout} />
        <ellipse cx={185.2} cy={51} rx={1.6} ry={2.7} fill={COLOR.eye} transform="rotate(-30 185.2 51)" />
        <ellipse cx={147} cy={76} rx={8.5} ry={5} fill={COLOR.blush} fillOpacity={mood === 'happy' ? 0.75 : 0.6} />
        <Eye mood={mood} />
        <Mouth mood={mood} />

        <Yuzu />
        <MoodExtras mood={mood} />
      </g>

      {bath && (
        <g>
          <path d={FRONT_WATER} fill={COLOR.water} />
          <path d={WATERLINE} fill="none" stroke={COLOR.waterHi} strokeWidth={2.5} strokeLinecap="round" />
          <g className="capy-ripple" fill="none" stroke={COLOR.waterHi} strokeWidth={2} strokeLinecap="round">
            {RIPPLES.map((r) => (
              <path key={r.d} d={r.d} strokeOpacity={r.opacity} />
            ))}
          </g>
          <g className="capy-steam" fill="none" strokeLinecap="round">
            {STEAM.map((d) => (
              <g key={d}>
                <path d={d} stroke={COLOR.waterHi} strokeOpacity={0.25} strokeWidth={5.5} />
                <path d={d} stroke={COLOR.steam} strokeWidth={2.8} />
              </g>
            ))}
          </g>
        </g>
      )}
    </svg>
  );
}
