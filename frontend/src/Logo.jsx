const Logo = ({ size = 30 }) => (
  <svg width={size * 1.6} height={size} viewBox="0 0 64 40" aria-hidden="true">
    <defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stopColor="#d9b98a" /><stop offset="1" stopColor="#8a6a43" /></linearGradient></defs>
    <path d="M20 8c-8 0-14 5-14 12s6 12 14 12c10 0 14-24 24-24 8 0 14 5 14 12s-6 12-14 12c-10 0-14-24-24-24z" fill="none" stroke="url(#g)" strokeWidth="5" strokeLinecap="round" />
  </svg>
);
export default Logo;
