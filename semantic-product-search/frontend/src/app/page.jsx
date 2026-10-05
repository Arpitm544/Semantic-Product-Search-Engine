import LandingPage from '@/components/LandingPage';
import catalog from '@/data/catalog.json';

export default function Home() {
  return <LandingPage catalog={catalog} />;
}
