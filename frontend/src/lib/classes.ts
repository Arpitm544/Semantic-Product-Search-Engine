/** Tailwind variants for class names selected dynamically by component state.
 * Keep utility strings literal so Tailwind can discover them at build time.
 */
const variants: Record<string, string> = {
  "approach-card": "pt-[24px] pr-[24px] pb-[24px] pl-[24px] [border:1px_solid_var(--border-d6e1d8)] [background:var(--surface-f2f6ef)] rounded-[12px] min-w-[0] [transition:border-color_.25s,_background_.25s,_transform_.25s] [&.is-selected]:[background:var(--surface-fdfef9)] [&.is-selected]:[border-color:var(--text-94b3a3)] [&.is-selected]:[transform:translateY(-3px)] [&.is-selected]:[box-shadow:0_12px_25px_var(--shadow-52755e0b)] [&_h3]:[font-style:normal] [&_h3]:[font-weight:normal] [&_h3]:text-[29px] [&_h3]:leading-[1.2] [&_h3]:[font-family:var(--serif)] [&_h3]:tracking-[-1px] [&_h3]:mt-[23px] [&_h3]:mr-[0] [&_h3]:mb-[14px] [&_h3]:ml-[0] [&_>_p]:text-[12px] [&_>_p]:leading-[1.9] [&_>_p]:[color:var(--text-4f624f)] [&_>_p]:mt-[13px] [&_>_p]:min-h-[94px] [&_>_footer]:[color:var(--text-53604f)] [&_>_footer]:text-[9px] [&_>_footer]:leading-[1.8] [&_>_footer]:pt-[19px] max-[1100.01px]:pt-[20px] max-[1100.01px]:pr-[20px] max-[1100.01px]:pb-[20px] max-[1100.01px]:pl-[20px] max-[1100.01px]:[&_h3]:text-[26px] max-[780.01px]:pt-[23px] max-[780.01px]:pr-[23px] max-[780.01px]:pb-[23px] max-[780.01px]:pl-[23px] max-[780.01px]:[&_>_p]:min-h-[unset] max-[780.01px]:[&_>_p]:text-[12px] motion-reduce:[&.is-selected]:[transform:none]",
  "brand": "inline-flex items-center gap-[9px] [font-family:var(--serif)] text-[28px] tracking-[-1.2px] max-[780.01px]:text-[26px]",
  "brand--light": "[color:var(--text-fff)]",
  "finish-swatch": "[border:3px_solid_var(--border-f3f7ef)] rounded-[50%] h-[24px] w-[24px] [box-shadow:0_0_0_1px_var(--shadow-c3cfc5)] pt-[0] pr-[0] pb-[0] pl-[0] [&.silver]:[background:var(--surface-cdd5d1)] [&.sage]:[background:var(--surface-92ab99)] [&.active]:[box-shadow:0_0_0_1px_var(--shadow-698772)]",
  "headphone-scene": "absolute [inset:5px_0_110px] z-[1] [&.is-ready::after]:[content:''] [&.is-ready::after]:absolute [&.is-ready::after]:bottom-[8%] [&.is-ready::after]:left-[24%] [&.is-ready::after]:w-[52%] [&.is-ready::after]:h-[4%] [&.is-ready::after]:rounded-[50%] [&.is-ready::after]:[background:var(--surface-647b7021)] [&.is-ready::after]:[filter:blur(12px)] [&.is-ready::after]:pointer-events-none [&.is-ready::after]:z-[-1]",
  "headphone-story": "mt-[78px] [&.is-simple_.story-track]:hidden [&.is-simple_.story-mobile]:block max-[780.01px]:[&_.story-track]:hidden max-[780.01px]:[&_.story-mobile]:block max-[780.01px]:mt-[55px] [@media(max-height:_720px)_and_(min-width:_781px)]:[&_.story-track]:hidden [@media(max-height:_720px)_and_(min-width:_781px)]:[&_.story-mobile]:block motion-reduce:[&_.story-track]:hidden motion-reduce:[&_.story-mobile]:block",
  "product-art": "w-[100%] h-[100%] [background-image:url('/images/catalog-art.png')] [background-size:200%_200%] bg-no-repeat [transition:transform_.7s_cubic-bezier(.2,.65,.3,1)] [&_svg]:w-[92%] [&_svg]:h-[92%]",
  "product-art--backpack": "[background-position:100%_0] [&.product-art--backpack]:[background-size:200%_206%]",
  "product-art--bottle": "[background-position:0_100%] [&.product-art--bottle]:[background-size:200%_194%]",
  "product-art--chair": "[&.product-art--chair]:[background:var(--surface-ece7de)]",
  "product-art--coffee": "[&.product-art--coffee]:[background:var(--surface-ece7de)]",
  "product-art--computer": "[&.product-art--computer]:[background:var(--surface-e2e7e6)]",
  "product-art--earbuds": "[&.product-art--earbuds]:[background:var(--surface-e6e2ee)]",
  "product-art--headphones": "[background-position:0_0] [&.product-art--headphones]:[background-size:200%_206%]",
  "product-art--jacket": "[background-position:100%_100%] [&.product-art--jacket]:[background-size:200%_194%]",
  "product-art--vector": "flex items-center justify-center [background:var(--surface-e5ebdf)]",
  "product-art--watch": "[&.product-art--watch]:[background:var(--surface-e6e2ee)]",
  "product-thumb": "w-[33px] h-[33px] rounded-[8px] grid place-items-center [font-style:normal] font-bold text-[12px] leading-[normal] [font-family:Manrope,sans-serif] [color:var(--text-657a60)] [background:var(--surface-eaf0e6)] shrink-[0]",
  "search-result-art": "overflow-hidden w-[76px] h-[76px] shrink-[0] grid place-items-center rounded-[10px] [background:var(--surface-e7efe4)] [color:var(--text-6f8869)] [font-style:normal] font-bold text-[26px] leading-[normal] [font-family:Manrope,sans-serif] [&_img]:w-[100%] [&_img]:h-[100%] [&_img]:object-contain [&_img]:[background:var(--surface-fff)] [&.art-1]:[background:var(--surface-f2eae1)] [&.art-1]:[color:var(--text-9a8067)] [&.art-2]:[background:var(--surface-eeedf5)] [&.art-2]:[color:var(--text-827da1)] [&.art-3]:[background:var(--surface-e7eff0)] [&.art-3]:[color:var(--text-69858a)] [&.art-4]:[background:var(--surface-f2e7e5)] [&.art-4]:[color:var(--text-a27e78)] max-[600.01px]:w-[55px] max-[600.01px]:h-[58px] max-[600.01px]:rounded-[8px] max-[600.01px]:text-[20px]",
  "story-visual": "relative rounded-[15px] min-w-[0] min-h-[360px] [background:radial-gradient(ellipse_at_60%_35%,_#f7f7f1_4%,_#dce7e8_48%,_#d2dedb_100%)] overflow-hidden",
  "story-visual--2": "[&.story-visual--2]:[background:radial-gradient(ellipse_at_50%_46%,_var(--surface-f0f4ee),_#dce6e5_73%)] [&_.headphone-scene::after]:opacity-[0]",
  "tone-1": "[&.tone-1]:[background:var(--surface-f2ece6)] [&.tone-1]:[color:var(--text-987b62)]",
  "tone-2": "[&.tone-2]:[background:var(--surface-ecebf4)] [&.tone-2]:[color:var(--text-797296)]",
  "tone-3": "[&.tone-3]:[background:var(--surface-e7eff1)] [&.tone-3]:[color:var(--text-64818c)]",
  "tone-4": "[&.tone-4]:[background:var(--surface-f3e9e6)] [&.tone-4]:[color:var(--text-a07870)]"
};

export function classes(value: string): string {
  return value.split(/\s+/).filter(Boolean).map(name => variants[name] ? name + ' ' + variants[name] : name).join(' ');
}
