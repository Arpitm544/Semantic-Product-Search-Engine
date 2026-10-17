const paths = {
  arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
  diagonal: <><path d="M6 18 18 6M6 6h12v12" /></>,
  down: <><path d="M12 4v16M6 14l6 6 6-6" /></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4.5 4.5" /></>,
  heart: <path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />,
  close: <><path d="m6 6 12 12M18 6 6 18" /></>,
  sliders: <><path d="M4 7h4m4 0h8M4 17h8m4 0h4" /><circle cx="10" cy="7" r="2" /><circle cx="14" cy="17" r="2" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  menu: <><path d="M4 8h16M4 16h16" /></>,
  leaf: <><path d="M20 3C7 2 3 8 5 15c2 7 16 4 15-12Z" /><path d="M4 21 15 10" /></>,
  sparkle: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" /></>,
};

export default function Icon({ name, size = 20, ...props }) {
  const icon = paths[name];
  if (!icon) {
    if (process.env.NODE_ENV !== 'production') console.warn(`Unknown icon name: ${name}`);
    return null;
  }

  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{icon}</svg>;
}
