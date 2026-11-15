'use client';
import { useEffect, useState } from 'react';
import AccountShell, { accountButton, accountInput, accountPanel } from '@/components/AccountShell';
import { ResourceStatus } from '@/components/AccountControls';
import { useAccountResource, type Preferences } from '@/lib/account';

export default function PreferencesPage() {
  const resource = useAccountResource<Preferences>('/api/preferences');
  const [form, setForm] = useState<Preferences | null>(null);
  const [categories, setCategories] = useState('');
  const [brands, setBrands] = useState('');
  useEffect(() => { if (resource.data) { setForm(resource.data); setCategories(resource.data.categories.join(', ')); setBrands(resource.data.brands.join(', ')); } }, [resource.data]);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form) return;
    const tags = (text: string) => text.split(',').map(item => item.trim()).filter(Boolean);
    await resource.mutate(() => resource.api('/api/preferences', { method: 'PUT', body: JSON.stringify({ ...form, categories: tags(categories), brands: tags(brands) }) }), 'Preferences saved for your next search.');
  }
  return <AccountShell active="/preferences" title="Your search preferences" description="Remember your budget and favorite categories and brands. You can turn these filters on or off for each search.">
    <ResourceStatus busy={resource.busy} error={resource.error} notice={resource.notice} retry={resource.reload} />
    {form && <form onSubmit={submit} className={`${accountPanel} max-w-3xl space-y-6`}><fieldset disabled={resource.busy} className="space-y-6">
      <div className="grid gap-5 sm:grid-cols-2"><label className="text-sm">Default search source<select className={`${accountInput} mt-2`} value={form.defaultSource} onChange={e => setForm({ ...form, defaultSource: e.target.value as 'mongo' | 'serpapi' })}><option value="mongo">Product catalog</option><option value="serpapi">Google Shopping</option></select></label>
        <label className="text-sm">Budget currency<select className={`${accountInput} mt-2`} value={form.currency} onChange={e => setForm({ ...form, currency: e.target.value })}>{['INR', 'USD', 'EUR', 'GBP', 'CAD', 'AUD', 'NZD', 'SGD', 'AED', 'CHF', 'JPY', 'CNY', 'HKD', 'SEK', 'NOK', 'DKK'].map(code => <option key={code}>{code}</option>)}</select></label>
        <label className="text-sm">Minimum budget (optional)<input className={`${accountInput} mt-2`} type="number" min="0" max="1000000000000" step="0.01" value={form.minBudget ?? ''} onChange={e => setForm({ ...form, minBudget: e.target.value === '' ? null : Number(e.target.value) })} /></label>
        <label className="text-sm">Maximum budget (optional)<input className={`${accountInput} mt-2`} type="number" min={form.minBudget ?? 0} max="1000000000000" step="0.01" value={form.maxBudget ?? ''} onChange={e => setForm({ ...form, maxBudget: e.target.value === '' ? null : Number(e.target.value) })} /></label></div>
      <label className="block text-sm">Preferred categories<input className={`${accountInput} mt-2`} value={categories} onChange={e => setCategories(e.target.value)} placeholder="Audio, Electronics" maxLength={2000} /><small className="mt-2 block opacity-65">Comma-separated exact category names; leave blank for all categories.</small></label>
      <label className="block text-sm">Preferred brands<input className={`${accountInput} mt-2`} value={brands} onChange={e => setBrands(e.target.value)} placeholder="Sony, Bose" maxLength={2000} /><small className="mt-2 block opacity-65">Up to 20 brands and 20 categories. Matching ignores letter case.</small></label>
      <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={form.inStockOnly} onChange={e => setForm({ ...form, inStockOnly: e.target.checked })} />Only products with known available stock</label>
      <label className="flex items-center gap-3 text-sm"><input type="checkbox" checked={form.applyByDefault} onChange={e => setForm({ ...form, applyByDefault: e.target.checked })} />Apply these preferences by default on new searches</label>
      <p className="text-xs leading-relaxed opacity-65">Budget filters use the selected currency, without currency conversion. Products with missing details for an active filter are excluded. Filters apply to the candidates returned by the search, so a narrow filter may show no results.</p>
      <div className="flex flex-wrap gap-3"><button className={accountButton}>Save preferences</button><button type="button" className={accountButton} onClick={() => resource.mutate(() => resource.api('/api/preferences', { method: 'DELETE' }), 'Preferences reset to defaults.')}>Reset to defaults</button><a className={accountButton} href="/search">Try a search ↗</a></div>
    </fieldset></form>}
  </AccountShell>;
}
