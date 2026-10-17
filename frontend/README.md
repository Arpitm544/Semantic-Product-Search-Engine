# Semantic landing page

An original, standalone ecommerce-inspired landing page for the Semantic Product Search Engine. Velorah inspired the atmosphere and serif typography; the layout, imagery, code, and product treatment were made for this project.

## Run

From the repository's `frontend/` folder, run:

    npm install
    npm run dev

This starts both the API and website. Open http://localhost:3001. To run only the API, use `python3 api/main.py` from `backend/`; to run only the frontend, use `npm run dev:frontend`. The API listens at `http://127.0.0.1:8000`. Set `NEXT_PUBLIC_API_URL` before starting the frontend to use a different backend URL. For a production preview:

    npm run build
    npm run start

`npm run start` serves only the frontend. Start the API separately with `python3 api/main.py` from `backend/` so the product search page can reach it.

The frontend uses Next.js, React, and Three.js. The catalog search uses the MongoDB product catalog with keyword and semantic retrieval, spelling correction, and reranking. The scroll story and the approach comparison remain illustrative examples, not live search results.

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
- Mobile screens, reduced-motion preferences, and browsers without WebGL use shorter illustrated chapters. The canvas loads near the story and pauses rendering off screen.
- The final keyword / semantic / hybrid comparison uses one scripted query. It explains the approaches; it is not a live ranking or performance benchmark.

## Structure

- public/images/: original generated imagery.
- public/models/: locally hosted AirPods Max GLB and its source/license attribution.
- src/app/: landing page, styles, and metadata.
- src/components/: landing sections, icons, and product artwork.
- src/components/HeadphoneStory.jsx, HeadphoneScene.jsx, and SearchComparison.jsx: the original scroll story, 3D scene with an imported model, and scripted comparison.
- src/data/catalog.json: static sample content.
- src/lib/format.js: INR price formatting.
- DESIGN.md: design notes and original image prompts.

No 21st.dev template source was downloaded or copied.
