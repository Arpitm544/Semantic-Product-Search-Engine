# Semantic landing page

An original, standalone ecommerce-inspired landing page for the Semantic Product Search Engine. Velorah inspired the atmosphere and serif typography; the layout, imagery, code, and product treatment were made for this project.

## Run

From the repository's `frontend/` folder, run:

    npm install
    npm run dev

This starts the API and website. If the project API is already running, it reuses
that process and starts only the website. Stopping this command leaves a reused
backend running. Open http://localhost:3001. To run only the API, use `python3 api/main.py` from `backend/`; to run only the frontend, use `npm run dev:frontend`. The API listens at `http://127.0.0.1:8000`. Set `NEXT_PUBLIC_API_URL` before starting the frontend to use a different backend URL. For a production preview:

    npm run build
    npm run start

`npm run start` serves only the frontend. Start the API separately with `python3 api/main.py` from `backend/` so the product search page can reach it.

The frontend uses Next.js 14, React 18, TypeScript, Tailwind CSS 4, and Three.js. Run `npm run typecheck` to check types without building. The catalog search uses the MongoDB product catalog with keyword and semantic retrieval, spelling correction, and reranking. The scroll story and the approach comparison remain illustrative examples, not live search results.

The `/search` page has a source selector for **MongoDB catalog** and **Google
Shopping · SerpApi**. Configure `SERPAPI_API_KEY` in `backend/.env` and restart the
backend to enable shopping requests (see the [backend setup](../backend/README.md#google-shopping-search-optional)).
The key is never required in frontend environment variables. Shopping cards show
images, original price labels, merchants, and external product links when
available. Missing or failed images use a placeholder. Switching sources clears
results and warnings. Google Shopping candidates pass through our semantic model
and reranker; successfully ranked cards show **Engine ranked**. If model ranking
fails, cards show **Google ranked** and a warning explains that Google's original
order is being shown. Switching sources cancels the previous frontend request.
Errors include a manual retry;
search requests time out after 45 seconds. Cancelling a frontend request does not
refund an upstream request that already started.

## Design behavior

- Hero and footer calls to action navigate to sections of this landing page.
- Inspiration links and collection tabs switch between four curated product previews, using a local static catalog snapshot.
- Product cards are visual previews, not search results or purchase controls. Prices are displayed in INR.
- The copy presents the project idea and visitor benefits. The connection illustration is decorative.
- Product artwork is illustrative because the sample catalog has no product images.
- Navigation supports mobile screens, keyboard focus, and reduced motion.
- Log in and Sign up appear in the desktop navbar and mobile navigation menu. Both open a local coming-soon dialog; no authentication service is connected. Escape, the close button, the backdrop, or “Theek hai” dismiss it, and focus returns to the triggering control.
- After the original hero, desktop scrolling advances through four chapters: a scripted search, the AirPods Max reveal/details, a schematic meaning map, and an illustrative match.
- The query “Apple headphones for a quieter commute” is typed as the visitor scrolls through the first chapter. “Find my headphones” advances to the product reveal without submitting a request. Mobile and reduced motion show the full query before the product image.
- The AirPods Max model is loaded from a local, optimized GLB with creator attribution. Drag it or use the arrow buttons; detail buttons and green/silver color studies are local visual controls. The story refers to the original generation, independently of the sample catalog.
- Mobile screens, reduced-motion preferences, and browsers without WebGL use shorter chapters with a still image of the same 3D model. The canvas loads near the story and pauses rendering off screen.
- The final keyword / semantic / hybrid comparison uses one scripted query. It explains the approaches; it is not a live ranking or performance benchmark.

## Styling

Page and component styles use Tailwind utilities in the TSX files. Exact pixel values and custom responsive breakpoints preserve the original design. `src/lib/classes.ts` contains complete utility strings for artwork variants and other classes selected by component state; avoid constructing Tailwind utilities from partial strings.

`src/app/globals.css` is the single stylesheet entry point. It imports Tailwind and keeps document defaults, design tokens, reduced-motion accessibility rules, and the two original animation keyframes. Tailwind Preflight is intentionally omitted to preserve the existing browser form defaults. The Three.js scroll animation retains its existing behavior. The product preview shows a still with a loading indicator until the first 3D frame renders, then crossfades into the canvas. Failed loads (including a 20-second loading timeout) and lost WebGL contexts keep the preview and offer **Retry 3D**. If the preview image also fails, a headphone icon and product name replace it. Reduced-motion visitors receive a static preview without a loading indicator.

## Structure

- public/images/: original generated imagery.
- public/models/: locally hosted AirPods Max GLB and its source/license attribution.
- src/app/: landing page, styles, and metadata.
- src/components/: landing sections, icons, and product artwork.
- src/components/HeadphoneStory.tsx, HeadphoneScene.tsx, and SearchComparison.tsx: the original scroll story, 3D scene with an imported model, and scripted comparison.
- src/data/catalog.json: static sample content.
- src/lib/format.ts: INR price formatting.
- DESIGN.md: design notes and original image prompts.

No 21st.dev template source was downloaded or copied.

Development output is stored in `.next-dev/`; production builds use `.next/`. This allows `npm run build` while the development server is running without overwriting its generated chunks.

### Color themes

The header theme toggle switches between the original light palette (default) and dark mode. The preference is saved as `semantic-theme` in local storage and restored before paint; it also follows changes from another tab. Color tokens live in `src/app/globals.css`, with dark values scoped to `data-theme="dark"`. Layout, artwork, Three.js materials, and motion preferences are shared between themes.

The refined dark palette uses semantic `--night-*` tokens for canvas, panels, text, borders, and sage actions. Selected comparison cards, form actions, and dashboard navigation have distinct dark states. Product photographs retain a light studio background; preview failures use a readable dark card. Theme changes from another tab, including clearing the saved preference, remain synchronized.
