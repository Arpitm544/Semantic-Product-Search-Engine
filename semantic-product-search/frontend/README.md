# Semantic landing page

A standalone Next.js landing page for the Semantic Product Search Engine. This foundation includes the responsive page shell, editorial hero, static product collections, and local interaction states. Product inspiration is loaded from a bundled catalog snapshot.

## Run locally

From this directory, run:

```sh
npm install
npm run dev
```

Open [http://localhost:3001](http://localhost:3001). To check a production build, run `npm run build` and then `npm run start`.

## Current behavior

- Collection tabs switch between curated groups of sample products.
- Navigation and calls to action move to sections on the page.
- Log in and Sign up open a local coming-soon dialog.
- Product cards are visual previews, with prices formatted in INR.
- The page does not connect to the search API or run model inference.

## Main folders

- `src/app/`: App Router entry points and page styles.
- `src/components/`: landing page sections, navigation, dialog, and product artwork.
- `src/data/catalog.json`: static product snapshot used by the preview.
- `public/images/`: original generated hero and catalog artwork.
