// Line icons. Decorative: always aria-hidden.
import type { ReactNode } from "react";

function Svg({ size, stroke = 2, view = "0 0 24 24", children }: {
  size: number; stroke?: number; view?: string; children: ReactNode;
}) {
  return (
    <svg width={size} height={size} viewBox={view} fill="none" stroke="currentColor" strokeWidth={stroke}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

export const ClockIcon = ({ size = 40, stroke = 2.2 }: { size?: number; stroke?: number }) => (
  <Svg size={size} stroke={stroke}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Svg>
);

export const ScanIcon = ({ size = 36 }: { size?: number }) => (
  <Svg size={size}><path d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M7 12h10" /></Svg>
);

export const FaceIdIcon = ({ size = 104 }: { size?: number }) => (
  <Svg size={size} stroke={2.6} view="0 0 48 48">
    <path d="M4 14V9a5 5 0 015-5h5M34 4h5a5 5 0 015 5v5M44 34v5a5 5 0 01-5 5h-5M14 44H9a5 5 0 01-5-5v-5" />
    <path d="M16 17v3M32 17v3M24 17v9h-2M17 32c4 3.5 10 3.5 14 0" />
  </Svg>
);

export const CheckIcon = ({ size = 44 }: { size?: number }) => (
  <Svg size={size} stroke={2.6}><path d="M5 12.5l4.5 4.5L19 7.5" /></Svg>
);

export const ChevronRight = ({ size = 18 }: { size?: number }) => (
  <Svg size={size} stroke={2.4}><path d="M9 5l7 7-7 7" /></Svg>
);

export const ChevronLeft = ({ size = 26 }: { size?: number }) => (
  <Svg size={size} stroke={2.4}><path d="M15 5l-7 7 7 7" /></Svg>
);

export const ShareIcon = ({ size = 24 }: { size?: number }) => (
  <Svg size={size}><path d="M12 3v12M8 7l4-4 4 4" /><path d="M6 11v8a1 1 0 001 1h10a1 1 0 001-1v-8" /></Svg>
);

export const PhoneIcon = ({ size = 24 }: { size?: number }) => (
  <Svg size={size}><rect x="7" y="2.5" width="10" height="19" rx="2.5" /><path d="M11 18.5h2" /></Svg>
);

export const KeypadIcon = ({ size = 22 }: { size?: number }) => (
  <Svg size={size}><rect x="3" y="6" width="18" height="12" rx="2" /><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10" /></Svg>
);

export const DeleteIcon = ({ size = 26 }: { size?: number }) => (
  <Svg size={size}><path d="M9 6h11a1 1 0 011 1v10a1 1 0 01-1 1H9l-6-6z" /><path d="M12 10l4 4M16 10l-4 4" /></Svg>
);

export const PaperIcon = ({ size = 36 }: { size?: number }) => (
  <Svg size={size}><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v4h4M10 12h5M10 16h5" /></Svg>
);

export const WifiOffIcon = ({ size = 36 }: { size?: number }) => (
  <Svg size={size}><path d="M2 8.5a15 15 0 0120 0M5 12a10.5 10.5 0 0114 0M8.5 15.5a5.5 5.5 0 017 0M12 19h.01M3 3l18 18" /></Svg>
);
