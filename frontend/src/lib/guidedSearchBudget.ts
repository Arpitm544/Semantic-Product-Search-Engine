import type { SearchProduct } from '@/lib/types';
import type { Refinement, RefinementGroup } from '@/lib/guidedSearch';

function confirmedPrice(product: SearchProduct) {
  const price = product.confirmedPrice;
  return price && Number.isFinite(price.amount) && price.amount >= 0 && typeof price.currency === 'string' &&
    /^[A-Z]{3}$/.test(price.currency) ? price : null;
}

function pricesByCurrency(products: SearchProduct[]) {
  const currencies = new Map<string, number[]>();
  for (const product of products) {
    const price = confirmedPrice(product);
    if (!price) continue;
    const amounts = currencies.get(price.currency) ?? [];
    amounts.push(price.amount);
    currencies.set(price.currency, amounts);
  }
  return currencies;
}

const cutoffFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 12 });

function budgetOption(currency: string, amounts: number[]): Refinement | null {
  const prices = [...new Set(amounts)].sort((a, b) => a - b);
  if (prices.length < 2) return null;
  const cutoff = prices[Math.floor((prices.length - 1) / 2)];
  return {
    id: `budget:${currency}:${cutoff}`,
    facet: 'budget',
    label: `Up to ${currency} ${cutoffFormat.format(cutoff)}`,
    matches: product => {
      const price = confirmedPrice(product);
      return price?.currency === currency && price.amount <= cutoff;
    },
  };
}

export function budgetGroup(products: SearchProduct[]): RefinementGroup {
  const options = [...pricesByCurrency(products)]
    .sort(([, a], [, b]) => b.length - a.length)
    .map(([currency, amounts]) => budgetOption(currency, amounts))
    .filter(option => option !== null)
    .slice(0, 3);
  return { facet: 'budget', label: 'Budget', options };
}
