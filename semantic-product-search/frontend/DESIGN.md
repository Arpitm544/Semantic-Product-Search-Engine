# Original visual direction

Velorah was an atmosphere reference: generous photographic space, calm pastel light, and editorial serif typography. No template code, layout assets, or source files were downloaded or copied. The new design uses the project name `semantic.`, actual sample product names, INR prices, everyday needs, and the project’s focus on meaningful product discovery.

The standalone landing page moves from an atmospheric hero and editorial collection into a concept illustration, an outdoor discovery composition, the project idea, and a final invitation to explore. Calls to action navigate between page sections; there are no API calls or ML integration. Custom artwork is clearly described as illustrative because the source catalog does not contain images.

CSS uses Georgia for display type and Arial/Helvetica for interface text, avoiding a remote font dependency. The page uses React, Next.js App Router, Three.js, plain CSS, and small original SVG icons. Motion respects reduced-motion preferences.

## Headphone scroll story

The original photographic hero remains at the top. Below it, a sticky scene follows one illustrative headphone from product details to an everyday query, a schematic vector space, and a possible match. The same example query appears in the final keyword / semantic / hybrid comparison.

The headphone uses a locally hosted AirPods Max GLB by Mr.Philin under CC BY 4.0, verified on the creator page and in embedded GLB metadata. Geometry is preserved; embedded textures are reduced to at most 1024px and encoded as WebP, reducing the download from 18.03 MB to 3.26 MB. Full source and license are in public/models/ATTRIBUTION.md, with visible credit below the story. The environment is procedural. The green finish uses the artist’s original textures; silver is a desaturated color study. The story uses original-generation AirPods Max details rather than the fictional catalog product, without claiming an Apple partnership or live catalog result.

The point cloud is deterministic illustrative geometry, not exported embeddings. Its distances and connections explain the concept without presenting measured similarity. Comparison cards have no synthetic scores or speed claims. There are no backend or ML calls.

Three.js is loaded near the story; rendering pauses when the canvas is off screen or the tab is hidden. Canvas resources are disposed when the scene unmounts. Mobile, reduced-motion, and WebGL-unavailable visitors see readable illustrated chapters instead of the long sticky sequence. AirPodsArtwork.jsx supplies an original lightweight SVG for these views and loading states.

## Product render

`public/images/airpods-max-render.jpg` is a screenshot of the locally rendered AirPods Max GLB in its silver color study. The Semantic and Hybrid comparison cards use this same product model rather than a separate illustration. It carries the model’s CC BY 4.0 attribution described in public/models/ATTRIBUTION.md.

## Generated assets

Generated with the built-in imagegen tool, then copied into this frontend. They are original artwork and not borrowed 21st.dev assets.

- `public/images/discovery-landscape.png`: panoramic editorial scene used in the hero.
- `public/images/catalog-art.png`: four-quadrant studio artwork, used as a CSS image sheet for headphones, backpack, bottle, and jacket. Other product types use original SVG artwork.

### Final hero prompt

```text
Use case: ads-marketing
Asset type: original wide photographic hero background for a premium semantic product discovery website.
Primary request: create a sophisticated atmospheric editorial ecommerce still life in a dreamlike outdoor environment, original composition not copying any reference or website.
Scene/backdrop: pale periwinkle blue dawn sky, soft lilac mist, layered distant alpine hills, pale limestone plateau in foreground, a hint of silvery grasses. Gentle haze and subtle photographic film texture.
Subjects: three generic unbranded products from a product-search catalog: beautifully sculptural brushed-silver over-ear headphones, a folded moss-green outdoor jacket, and a matte pale blue stainless water bottle. Place these together as an editorial product installation on low natural stone platforms in the lower quarter of the scene. Products visibly realistic, elegant, unobstructed, naturally grounded with soft shadows. No people.
Composition: very wide horizontal landscape, premium advertising photography, large calm open sky across upper two thirds with NO objects in that area so white headline and a search box can be overlaid by the website; product installation across lower third, foreground fills lower edge. Scenic depth, not a flat studio background. Use a slightly moody medium blue sky at the top for white text readability while retaining pale lilac light at horizon.
Lighting/mood: soft dawn glow, quiet discovery, cinematic but tasteful, restrained pastel colors with a slate blue cast.
Constraints: no text, no logos, no letters, no UI, no watermarks, no robots, no glowing neon, no noisy sci-fi imagery, no camper van. Landscape 16:9 or wider.
```

### Final catalog artwork prompt

```text
Use case: product-mockup
Asset type: four-quadrant square product art sheet for a premium ecommerce product discovery demo.
Create a square 2 by 2 contact sheet with four exactly equal square quadrants and NO gutters, borders, text or labels. Each quadrant contains ONE centered unbranded product in premium photorealistic studio advertising photography, generous space around each object, subtle grounding shadows, fully visible product.
Top LEFT: sculptural brushed silver over-ear wireless headphones, front three-quarter angle, pale warm ivory background.
Top RIGHT: sage green 40 liter hiking backpack, three-quarter front view with realistic straps, pale muted sage background.
Bottom LEFT: matte pale slate-blue insulated stainless steel 1L water bottle with silver cap, very light blue-grey background.
Bottom RIGHT: moss-green insulated winter parka jacket hanging as a three-dimensional torso shape without person or hanger visible, hood and zip detailed, pale muted lavender background.
Lighting: large softbox, editorial fashion product photography, restrained colors, crisp materials and fabric texture, grounded not floating. EXACT 2x2 layout aligned at center, flat uniform backgrounds within each quadrant. Avoid logos, people, brand names, written UI, numbers or watermarks. Product artwork is illustrative for a fictional catalog.
```
