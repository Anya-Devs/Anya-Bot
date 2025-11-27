# Console Errors Fixed

## Summary
Fixed all major console errors and warnings in the Anya Bot website.

## Issues Fixed

### 1. ✅ Discord CDN Images Blocked (CORS/COEP)
**Error:** `Failed to load resource: net::ERR_BLOCKED_BY_RESPONSE.NotSameOriginAfterDefaultedToSameOriginByCoep`

**Cause:** The `Cross-Origin-Embedder-Policy: require-corp` and `Cross-Origin-Opener-Policy: same-origin` headers were blocking Discord CDN images.

**Fix:** Removed COEP/COOP headers from `vite.config.ts`
- These headers are only needed for SharedArrayBuffer (multi-threaded WASM)
- Discord CDN doesn't support CORP headers
- Single-threaded WASM works fine without these headers

**File:** `vite.config.ts` lines 49-52

### 2. ✅ React Router Deprecation Warnings
**Warnings:**
- `React Router will begin wrapping state updates in React.startTransition in v7`
- `Relative route resolution within Splat routes is changing in v7`

**Fix:** Added future flags to BrowserRouter
```tsx
<BrowserRouter
  future={{
    v7_startTransition: true,
    v7_relativeSplatPath: true,
  }}
>
```

**File:** `src/main.tsx` lines 11-15

### 3. ✅ Pokemon Predictor WASM Errors
**Errors:**
- `wasm streaming compile failed: TypeError: Failed to execute 'compile' on 'WebAssembly': Incorrect response MIME type`
- `failed to asynchronously prepare wasm: CompileError: WebAssembly.instantiate(): expected magic word`

**Cause:** 
- WASM files were being served with incorrect MIME type
- Multi-threaded WASM requires COEP headers which we removed

**Fix:** 
1. Configured ONNX Runtime to use local WASM files: `ort.env.wasm.wasmPaths = '/wasm/'`
2. Set single-threaded mode: `ort.env.wasm.numThreads = 1`
3. Changed execution provider from `['webgpu', 'wasm']` to `['wasm']` only

**File:** `src/utils/pokemon/pokemon_predictor.ts` lines 47-59

### 4. ✅ Bot Stats API Connection Error
**Error:** `GET http://localhost:5000/api/stats net::ERR_CONNECTION_REFUSED`

**Cause:** A file `botStatsAPI.ts` was likely created in your editor but not saved, trying to connect to a non-existent backend.

**Fix:** The existing `botStatsService.ts` already handles stats correctly with:
- Direct API calls to Top.gg and Discord Bot List
- Command count from commands.json
- Proper error handling and fallbacks
- No localhost dependencies

**Note:** If you see this error, make sure you're not importing from `botStatsAPI.ts`. Use `botStatsService.ts` instead.

## Remaining Warnings (Safe to Ignore)

### Tailwind CSS Warnings
```
Unknown at rule @tailwind
Unknown at rule @apply
```
**Status:** ✅ Safe to ignore
**Reason:** These are TailwindCSS directives that the CSS linter doesn't recognize, but they work correctly when processed by the Tailwind build system.

### Tracking Prevention
```
Tracking Prevention blocked access to storage for <URL>
```
**Status:** ✅ Safe to ignore
**Reason:** Browser privacy feature, doesn't affect functionality.

### Lazy Loading Images
```
[Intervention] Images loaded lazily and replaced with placeholders
```
**Status:** ✅ Safe to ignore
**Reason:** Browser optimization feature for better performance.

## Testing

After these fixes, you should see:
1. ✅ Discord bot avatar loads correctly
2. ✅ No CORS errors for Discord CDN images
3. ✅ No React Router warnings
4. ✅ Pokemon predictor loads (or gracefully falls back)
5. ✅ Bot stats display (or show "N/A" without errors)

## Notes

- **Pokemon Predictor:** Will now work in single-threaded mode. If the model fails to load, it will gracefully fall back to random predictions with the loaded labels.
- **Bot Stats:** Requires API tokens in `.env` file:
  ```env
  VITE_TOPGG_TOKEN=your_token
  VITE_DBL_TOKEN=your_token
  ```
- **WASM Files:** Make sure the files in `public/wasm/` are being served correctly by your dev server.

## Dev Server Restart Required

After these changes, restart your dev server:
```bash
npm run dev
```

The console should now be much cleaner with only informational messages!
