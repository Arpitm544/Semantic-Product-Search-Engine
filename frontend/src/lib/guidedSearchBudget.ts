import type { SearchProduct } from '@/lib/types';
import type { Refinement, RefinementGroup } from '@/lib/guidedSearch';

function confirmedPrice(product: SearchProduct) {
  const price = product.confirmedPrice;
  return price && Number.isFinite(price.amount) && price.amount >= 0 && typeof price.currency === 'string' &&
    /^[A-Z]{3}$/.test(price.currency) ? price : null;
}

export function budgetGroup(products: SearchProduct[]): RefinementGroup {
  const currencies = new Map<string, number[]>();
  for (const product of products) {
    const price = confirmedPrice(product);
    if (!price) continue;
    const amounts = currencies.get(price.currency) ?? [];
    amounts.push(price.amount);
    currencies.set(price.currency, amounts);
  }
  const options: Refinement[] = [];
  for (const [currency, amounts] of [...currencies].sort(([, a], [, b]) => b.length - a.length)) {
    const prices = [...new Set(amounts)].sort((a, b) => a - b);
    // Offer a cutoff from the lower half of actual prices, below the highest price.
    if (prices.length < 2) continue;
    const cutoff = prices[Math.floor((prices.length - 1) / 2)];
    const display = new Intl.NumberFormat('en-US', { maximumFractionDigits: 12 }).format(cutoff);
    options.push({
      id: `budget:${currency}:${cutoff}`, facet: 'budget', label: `Up to ${currency} ${display}`,
      matches: product => {
        const price = confirmedPrice(product);
        return price?.currency === currency && price.amount <= cutoff;
      },
    });
    if (options.length === 3) break;
  }
  return { facet: 'budget', label: 'Budget', options };
}
