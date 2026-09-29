/**
 * Simple product illustrations (not photos). The blueprint forbids stock photos
 * and pictures we don't own, so these are clearly labelled illustrations until
 * real photos of the approved samples exist.
 */
const OAK = "#c89a67";
const OAK_DARK = "#9b7148";
const WALNUT = "#6b4a33";
const FELT = "#8a8f87";
const LEATHER = "#3b3a36";
const STEEL = "#4a4f55";
const DESK = "#efe7da";
const INK = "#2b2926";

function Desk() {
  return (
    <>
      <rect x="0" y="0" width="400" height="300" fill="#f5efe6" />
      <rect x="20" y="200" width="360" height="14" rx="3" fill={DESK} stroke="#d9cdb9" />
      <rect x="40" y="214" width="8" height="70" fill="#d9cdb9" />
      <rect x="352" y="214" width="8" height="70" fill="#d9cdb9" />
    </>
  );
}

function Mat() {
  return (
    <g>
      <rect x="70" y="186" width="260" height="14" rx="4" fill={LEATHER} />
      <rect x="74" y="184" width="252" height="10" rx="3" fill={FELT} />
      <rect x="78" y="186" width="244" height="5" rx="2" fill="none" stroke="#b9bdb5" strokeDasharray="4 3" />
      <rect x="150" y="176" width="90" height="10" rx="2" fill={INK} opacity="0.85" />
      <ellipse cx="270" cy="181" rx="10" ry="6" fill={INK} opacity="0.85" />
    </g>
  );
}

function Tray() {
  return (
    <g>
      <path d="M110 218 h180 v26 a6 6 0 0 1 -6 6 h-168 a6 6 0 0 1 -6 -6z" fill={STEEL} />
      <rect x="120" y="222" width="40" height="18" rx="3" fill="#e9e4dc" />
      <path d="M160 231 C 200 245, 230 225, 280 238" stroke={INK} strokeWidth="3" fill="none" />
      <rect x="108" y="206" width="10" height="16" fill={STEEL} />
      <rect x="282" y="206" width="10" height="16" fill={STEEL} />
    </g>
  );
}

function Clips() {
  return (
    <g>
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(${250 + i * 30} 184)`}>
          <rect width="22" height="16" rx="5" fill={WALNUT} />
          <rect x="7" y="2" width="8" height="5" rx="2" fill="#2f2f2f" />
        </g>
      ))}
      <path d="M261 186 C 261 150, 330 170, 380 120" stroke={INK} strokeWidth="2.5" fill="none" />
      <path d="M291 186 C 300 160, 340 170, 390 150" stroke={INK} strokeWidth="2.5" fill="none" />
    </g>
  );
}

function Riser() {
  return (
    <g>
      <rect x="120" y="160" width="160" height="40" rx="4" fill={OAK} />
      <rect x="170" y="176" width="60" height="16" rx="2" fill={OAK_DARK} />
      <rect x="192" y="182" width="16" height="3" rx="1.5" fill="#f5efe6" />
      <rect x="150" y="60" width="100" height="70" rx="4" fill={INK} />
      <rect x="156" y="66" width="88" height="58" rx="2" fill="#9fb0a8" />
      <rect x="195" y="130" width="10" height="22" fill={INK} />
      <rect x="175" y="150" width="50" height="10" rx="2" fill={INK} />
    </g>
  );
}

const SCENES: Record<string, () => React.ReactElement> = {
  "desk-mat": () => <Mat />,
  "cable-tray": () => <><Mat /><Tray /></>,
  "cable-clips": () => <Clips />,
  "monitor-riser": () => <Riser />,
  "desk-reset": () => <><Mat /><Tray /><Clips /></>,
  hero: () => <><Riser /><Mat /><Tray /><Clips /></>,
};

export default function Illustration({ id, caption = true }: { id: string; caption?: boolean }) {
  const Scene = SCENES[id] ?? SCENES["desk-mat"];
  return (
    <figure className="illustration">
      <svg viewBox="0 0 400 300" role="img" aria-label="Illustration of the product">
        <Desk />
        <Scene />
      </svg>
      {caption && <figcaption>Illustration. Real photos come from the approved sample.</figcaption>}
    </figure>
  );
}
