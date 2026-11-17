import LandingPage from '@/components/LandingPage';
import catalog from '@/data/catalog.json';
import { landingCollections } from '@/lib/landingCollections';

export default function Home() {
  const productIds = new Set(landingCollections.flatMap(collection => collection.ids));
  return <LandingPage catalog={catalog.filter(product => productIds.has(product.id))} />;
}
