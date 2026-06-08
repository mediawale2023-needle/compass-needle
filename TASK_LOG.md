# Task Log

Chronological log of completed repository work. Read before making changes to understand recent context.

## Entry Template

- Date: YYYY-MM-DD
- Request:
- Summary:
- Files touched:
- Risks or follow-ups:

## Entries

- Date: 2026-06-06
- Request: Push the aspirant `Schemes` restriction and duplicate `Settings` cleanup to GitHub.
- Summary: Pushed commit `b0d7af3c` (`Restrict schemes for aspirant accounts`) to `origin/main`, publishing elected-only `Schemes` access in both sidebar navigation and `/dashboard/schemes`, while removing the duplicate module-level `Settings` item so only the `System` copy remains.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a navigation/access-control deploy. If `Schemes` should later return for aspirants in a limited form, update `canAccessSchemes()` rather than restoring route-specific exceptions.

- Date: 2026-06-06
- Request: Hide `Schemes` from aspirant logins and remove the duplicate `Settings` tab in the MP sidebar.
- Summary: Added a shared `canAccessSchemes()` helper, used it to hide `Schemes` for aspirant accounts in `Sidebar.js`, removed the duplicate module-level `Settings` entry so only the `System` copy remains, and guarded `/dashboard/schemes` so aspirants are redirected back to `/dashboard`.
- Files touched: `frontend/lib/account.js`, `frontend/components/Sidebar.js`, `frontend/app/dashboard/schemes/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is a navigation and route-access cleanup. If `Schemes` should later return for aspirants in a limited mode, expand `canAccessSchemes()` rather than restoring one-off UI exceptions.

- Date: 2026-06-06
- Request: Push the slight upward adjustment to the MP dashboard sidebar brand lockup.
- Summary: Pushed commit `1f0d45cd` (`Lift MP sidebar brand lockup`) to `origin/main`, publishing the trimmed top padding and slightly tighter internal gap so the `Compass Needle` sidebar header sits a bit higher.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a minimal shell-spacing deploy. If the brand block still feels low after refresh, the next pass should make another small padding-only adjustment rather than changing the logo or wordmark scale.

- Date: 2026-06-06
- Request: Move the `Compass Needle` lockup slightly upward in the MP dashboard sidebar.
- Summary: Adjusted the MP sidebar header spacing in `frontend/components/Sidebar.js` by trimming the top padding and slightly reducing the gap between the cream logo and the stacked wordmark so the brand block sits a bit higher without changing the overall sidebar structure.
- Files touched: `frontend/components/Sidebar.js`, `TASK_LOG.md`
- Risks or follow-ups: This is a very small layout-only tweak. If the header still feels low after deploy, the next step should be another minimal padding adjustment rather than changing typography or logo scale.

- Date: 2026-06-06
- Request: Push the admin login brand-lockup alignment to GitHub.
- Summary: Pushed commit `92667037` (`Align admin login brand lockup`) to `origin/main`, publishing the MP-style centered logo treatment and simplified title/subtitle rhythm for the admin login page.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a login-surface polish deploy only. If the admin sign-in screen now feels too neutral, the next step should add subtle admin-specific tone through color or spacing rather than reopening the shared logo structure.

- Date: 2026-06-06
- Request: Make the admin login page typography and logo lockup feel similar to the MP login page.
- Summary: Updated `admin/app/page.js` so the admin login header now uses the same larger centered logo treatment as the MP login page, with a width-controlled `object-contain` logo wrapper and simpler heading/subtitle typography to match the MP product rhythm more closely.
- Files touched: `admin/app/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This is a UI-only alignment pass. If the admin login page now feels too plain relative to the rest of the admin design language, the next step should tune subtle color/letterspacing rather than reverting the shared lockup structure.

- Date: 2026-06-06
- Request: Push the shared login logo asset centering fix to GitHub.
- Summary: Pushed commit `0605269c` (`Center shared login logo asset`) to `origin/main`, publishing the tighter-cropped `needle-logo.svg` canvas for both MP and admin login surfaces so the visible mark can center correctly inside the existing layout.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is an asset-bounds deploy. If the logo still feels off after refresh, the next step should inspect the visible geometry or lockup proportions rather than outer wrapper centering.

- Date: 2026-06-06
- Request: Fix the shared login logo asset so it is truly centered instead of appearing shifted inside a centered wrapper.
- Summary: Trimmed the oversized SVG canvas on `needle-logo.svg` in both `frontend/public` and `admin/public`, removing the excessive right-side whitespace that was making the MP/admin login logo look off-center even after wrapper-level centering fixes.
- Files touched: `frontend/public/needle-logo.svg`, `admin/public/needle-logo.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is a shared branding-asset correction. If centering still feels off after deploy, the next inspection should compare the visible geometry itself against the desired lockup rather than adjusting outer layout again.

- Date: 2026-06-06
- Request: Push the MP login logo centering refinement to GitHub.
- Summary: Pushed commit `fc11dd58` (`Center MP login logo lockup`) to `origin/main`, publishing the width-controlled centered logo wrapper and tighter logo-to-heading spacing for the MP login card.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is still a presentation-only deploy. If the logo continues to feel optically off-center after refresh, the next inspection should focus on the SVG's internal whitespace rather than outer layout.

- Date: 2026-06-06
- Request: Correct the MP login header again so the logo is visually centered and the gap to `Compass Needle` is tighter.
- Summary: Refined the MP login header in `frontend/app/page.js` by placing the logo inside a width-controlled centered wrapper, reducing the logo-to-title gap again, and tightening `CardHeader` vertical spacing so the brand lockup reads more like a single unit on mobile.
- Files touched: `frontend/app/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This is still a presentation-only tweak. If the lockup still looks off after deploy, the next step should inspect the SVG's internal whitespace rather than continuing to adjust outer spacing alone.

- Date: 2026-06-06
- Request: Push the MP login header spacing refinement to GitHub.
- Summary: Pushed commit `4f359f2b` (`Refine MP login header spacing`) to `origin/main`, publishing the centered `object-contain` login-logo treatment with slightly more top breathing room and a tighter handoff into the `Compass Needle` heading.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a visual rhythm deploy only. If the login card still feels too tall after review, the next tweak should trim header spacing before revisiting logo size.

- Date: 2026-06-06
- Request: Refine the MP login header so the enlarged logo stays centered, slightly lower, and closer to the heading without losing whitespace above.
- Summary: Tuned the MP login `CardHeader` spacing in `frontend/app/page.js` by adding a little more top padding, reducing the gap below the logo, and explicitly using `object-contain` on the DS-3 logo image. The title and subtitle remain centered, and the logo keeps its aspect ratio on mobile.
- Files touched: `frontend/app/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This is a visual rhythm adjustment only. If the sign-in card still feels too tall on smaller phones, the next step should be fine-tuning header padding rather than resizing the logo again.

- Date: 2026-06-06
- Request: Push the enlarged MP login logo update to GitHub.
- Summary: Pushed commit `04ee64a9` (`Increase MP login logo prominence`) to `origin/main`, publishing the MP login card branding tweak that increases the `needle-logo.svg` treatment from `h-14 w-auto` to `h-16 w-auto`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a small visual-only deploy. If the sign-in card feels vertically heavy after refresh, the next refinement should reduce surrounding spacing rather than shrinking the logo again.

- Date: 2026-06-06
- Request: Increase the MP login page logo to roughly 50% above the original baseline.
- Summary: Updated the MP login logo in `frontend/app/page.js` from `h-14 w-auto` to `h-16 w-auto`, giving the DS-3 logo more prominence in the sign-in card while keeping its aspect ratio and centered layout intact.
- Files touched: `frontend/app/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This is a small visual-only tweak, but it makes the login header taller. If the card feels too vertically heavy after deploy, the next adjustment should trim surrounding spacing rather than shrinking the logo asset again.

- Date: 2026-06-06
- Request: Increase the MP login page logo size to `h-14 w-auto`.
- Summary: Updated the MP login page logo in `frontend/app/page.js` from `h-11 w-auto` to `h-14 w-auto` so the DS-3 logo has more presence in the sign-in card without changing the asset itself.
- Files touched: `frontend/app/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This is a small visual-only tweak. If the login card header feels too tall after deploy, the next adjustment should be spacing around the logo rather than changing the logo asset again.

- Date: 2026-06-06
- Request: Apply the approved Compass Needle logo system to the admin sidebar, MP login page, and admin login page.
- Summary: Replaced the remaining placeholder compass/icon treatments with the approved DS-3 brand assets across the admin sidebar and both login pages. The admin rail now uses the cream stacked lockup, and the MP/admin login screens use the ink logo on their light surfaces for consistent cross-surface branding.
- Files touched: `admin/components/Sidebar.js`, `frontend/app/page.js`, `admin/app/page.js`, `frontend/public/needle-logo.svg`, `admin/public/needle-logo.svg`, `admin/public/needle-logo-cream.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is a branding consistency pass only. If any of the auth cards now feel visually unbalanced, the next work should tune spacing/typography around the logo rather than swapping the logo treatment again.

- Date: 2026-06-06
- Request: Push the `Compass Needle Design System-3` MP shell pass to GitHub for deployment.
- Summary: Pushed commit `6e03be58` (`Apply DS-3 MP shell chrome`) to `origin/main`, publishing the DS-3-inspired MP shell updates: cream logo asset, stacked sidebar brand lockup, and top-bar shell polish while preserving existing dashboard cards and data flows.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy intentionally changes shell chrome rather than card internals. If any section still feels visually inconsistent with DS-3, the next pass should target specific dashboard components instead of reopening the shell again.

- Date: 2026-06-06
- Request: Implement the `Compass Needle Design System-3` dashboard shell for the MP console.
- Summary: Updated the MP shell to follow the DS-3 console chrome by introducing the cream brand asset, a stacked sidebar lockup, and lighter top-bar polish while preserving the existing dashboard data flows and cards. The change focused on shell-level framing rather than a deep card-by-card redesign.
- Files touched: `frontend/components/Sidebar.js`, `frontend/app/dashboard/layout.js`, `frontend/public/needle-logo-cream.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is intentionally a shell pass. If any dashboard sections still feel off relative to DS-3, the next work should target specific cards/components instead of reopening the overall chrome again.

- Date: 2026-06-06
- Request: Push the rollback to the original MP dashboard orange sidebar logo.
- Summary: Pushed commit `d88968dc` (`Restore original MP sidebar logo`) to `origin/main`, publishing the rollback from the experimental logo/header iterations back to the original orange `क` badge and one-line `Compass Needle` header.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This intentionally restores the known-good baseline. Any future sidebar branding change should start from a complete approved lockup design, not incremental experiments on the live header.

- Date: 2026-06-06
- Request: Revert the MP dashboard sidebar branding experiments and restore the original orange logo.
- Summary: Rolled back the sidebar logo and header lockup changes, restoring the original orange `क` badge and the simpler one-line `Compass Needle` header in `frontend/components/Sidebar.js`. Also reset project memory to treat that original badge as the current stable baseline.
- Files touched: `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The experimental `frontend/public/compass-needle-mark.svg` asset may remain in the tree, but it is no longer used by the sidebar. Any future brand refresh should start as a full approved lockup pass rather than incremental asset swaps.

- Date: 2026-06-06
- Request: Push the stacked MP sidebar brand lockup fix to GitHub for deployment.
- Summary: Pushed commit `72b5ef92` (`Stack MP sidebar brand lockup`) to `origin/main`, publishing the vertical expanded-state brand header so the sidebar no longer clips `Compass Needle` on mobile-width drawers.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Live review should confirm the stacked lockup solves the visual breakage without making the top of the sidebar feel too tall, but future branding changes should preserve this mobile-safe lockup pattern.

- Date: 2026-06-06
- Request: Fix the MP dashboard header lockup so the logo and wordmark fit cleanly on the mobile-width sidebar.
- Summary: Reworked the sidebar brand header into a vertical lockup for the expanded state, with the mark above stacked `Compass` / `Needle` lines and the meta line underneath, while keeping a compact icon-only treatment for the collapsed desktop rail. This fixes the mobile clipping that made the sidebar still feel broken after the logo asset was corrected.
- Files touched: `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Live review should confirm the new stacked lockup feels balanced against the rest of the sidebar navigation, but future tweaks should now focus on typography/spacing rather than more logo-asset rescues.

- Date: 2026-06-06
- Request: Push the wide, landscape MP sidebar logo treatment to GitHub for deployment.
- Summary: Pushed commit `32eb3289` (`Use wide MP sidebar logo treatment`) to `origin/main`, publishing the landscape logo proportions and wider `Sidebar.js` wrapper so the source mark is no longer squeezed into a square badge slot.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Live review should confirm the wider mark now looks correct on both mobile and desktop sidebars and that no future tweak shrinks it back into a square slot.

- Date: 2026-06-06
- Request: Stop squeezing the MP dashboard logo into a square slot and use a wider source-accurate treatment.
- Summary: Replaced the sidebar asset with a landscape SVG that follows the original logo proportions and widened the `Sidebar.js` logo wrapper so the arch and compass needle render without square-badge distortion. Kept the rest of the sidebar header layout unchanged.
- Files touched: `frontend/public/compass-needle-mark.svg`, `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Live review should confirm the wider mark still balances well against the wordmark on mobile, but future fixes should preserve the landscape treatment rather than returning to square icon framing.

- Date: 2026-06-06
- Request: Push the transparent standalone MP sidebar logo treatment to GitHub for deployment.
- Summary: Pushed commit `743d1542` (`Use transparent MP sidebar logo mark`) to `origin/main`, publishing the transparent source-based mark plus the slightly roomier sidebar logo wrapper so the MP sidebar no longer renders the logo as a boxed beige tile.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Live review should confirm the transparent mark now feels correct on the dark sidebar in both mobile and desktop states, but future refinements should continue to tune wrapper sizing before altering the underlying source geometry again.

- Date: 2026-06-06
- Request: Fix the MP dashboard logo treatment so it uses the standalone mark instead of a boxed beige tile.
- Summary: Rebuilt `frontend/public/compass-needle-mark.svg` as a transparent standalone mark based on the source artwork and widened the `Sidebar.js` logo wrapper to let the mark breathe at sidebar size. This removes the faux app-icon tile look that was making the live logo feel wrong even after the source geometry was deployed.
- Files touched: `frontend/public/compass-needle-mark.svg`, `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Live review should confirm the transparent mark has enough contrast and spacing on both mobile and desktop sidebar states, but future tweaks should start with wrapper sizing rather than reboxing the asset.

- Date: 2026-06-06
- Request: Push the source-based MP dashboard sidebar logo asset to GitHub for deployment.
- Summary: Pushed commit `b5ac7392` (`Use source MP sidebar logo asset`) to `origin/main`, publishing the `Needle Logo.zip` `logo.html` geometry as the new `frontend/public/compass-needle-mark.svg` instead of the earlier approximations.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Live verification should confirm Vercel is serving the new asset and that the source-accurate geometry reads cleanly inside the compact sidebar tile.

- Date: 2026-06-06
- Request: Replace the MP dashboard sidebar logo with the actual source geometry from the provided zip asset and push it live.
- Summary: Rebuilt `frontend/public/compass-needle-mark.svg` from the real geometry inside `Needle Logo.zip` `logo.html`, replacing the earlier approximations while keeping the `Sidebar.js` integration unchanged. This makes the sidebar logo source-accurate without disturbing the sidebar layout.
- Files touched: `frontend/public/compass-needle-mark.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Live review should still confirm the source-accurate mark reads well at the small sidebar size, but future fixes should now start from the same source artwork rather than approximate redraws.

- Date: 2026-06-06
- Request: Push the repaired MP dashboard sidebar logo asset to GitHub for deployment.
- Summary: Pushed commit `8f8aead8` (`Refine MP sidebar logo asset`) to `origin/main`, publishing the cleaner vector replacement for `frontend/public/compass-needle-mark.svg` after the first live logo render looked damaged.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Live review should focus on the rendered logo at the small sidebar size because the code path is unchanged and only the SVG geometry was refined.

- Date: 2026-06-06
- Request: Repair the MP dashboard sidebar logo because the first SVG asset looked damaged live.
- Summary: Replaced the initial rough `frontend/public/compass-needle-mark.svg` with a cleaner reference-matched vector while keeping the existing `Sidebar.js` integration unchanged, so only the logo geometry changed and the sidebar layout stayed stable.
- Files touched: `frontend/public/compass-needle-mark.svg`, `TASK_LOG.md`
- Risks or follow-ups: The logo should be visually rechecked at the small sidebar size on live Vercel because this fix depends on how the refined geometry reads at roughly `32px`.

- Date: 2026-06-06
- Request: Push the MP dashboard sidebar logo refresh to GitHub for deployment.
- Summary: Pushed commit `dae39cbb` (`Replace MP sidebar logo mark`) to `origin/main`, publishing the MP sidebar branding swap from the old orange text badge to the reusable `frontend/public/compass-needle-mark.svg` asset rendered in `Sidebar.js`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Live verification should confirm the Vercel MP frontend has picked up the new asset and that the logo remains visually balanced in both expanded and collapsed sidebar states.

- Date: 2026-06-06
- Request: Replace the MP dashboard sidebar's orange text badge with the new Compass Needle logo.
- Summary: Added a reusable sidebar logo asset at `frontend/public/compass-needle-mark.svg` and updated `frontend/components/Sidebar.js` to render it with `next/image` while preserving the existing compact sidebar footprint in both expanded and collapsed states.
- Files touched: `frontend/public/compass-needle-mark.svg`, `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The logo now depends on the bundled asset path, so any future brand refinement should update the SVG rather than reintroducing inline text styling. Visual QA should confirm the mark feels balanced against the sidebar typography on both desktop and mobile.

- Date: 2026-06-05
- Request: Push the generalized building-text locality resolver upgrade to GitHub for deployment.
- Summary: Pushed commit `929a921b` (`Recover locality aliases from building text`) to `origin/main`, publishing the resolver improvement that safely promotes locality-like `building_name` phrases into match aliases and prefers richer matched locality names over abbreviated polling-sheet labels.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Live verification should focus on plain-text cases where the uploaded geography row is abbreviated but the fuller citizen-facing locality appears in polling building text, and confirm no new false positives appear around generic container words like `nagar` or `colony`.

- Date: 2026-06-05
- Request: Make plain-text locality mapping recover fuller citizen-facing names when the uploaded geography row is abbreviated but the detailed locality exists inside polling-sheet building text.
- Summary: Extended `modules/geography_resolver.py` so locality-looking `building_name` lines become safe alias seeds for matching, while generic venue/classroom lines are ignored. Also changed resolved display-value selection to prefer the richer matched alias over an abbreviated source locality when the alias is clearly more specific. Added generalized regressions for abbreviated-row recovery, stage-prefix trimming, and generic venue-line rejection, and verified the plain-text `rani chennamma nagar...` case now resolves to `Belgaum Dakshin` with `matched_value = Rani Channamma Nagar`.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The new extraction path is intentionally narrow to avoid indexing arbitrary building labels. Before production deploy, live verification should include a few non-Belagavi plain-text cases with abbreviated uploaded localities to confirm the generic heuristics help without creating new `... nagar`/`... colony` false positives.

- Date: 2026-06-05
- Request: Add a dedicated response path for personal/discretionary requests like transfer, admission, and private family/property help.
- Summary: Added narrow first-person discretionary-request detection for transfer requests, admission help, recommendation/sifarish asks, and private family/property disputes. Those messages now save as `Personal Request`, skip location-demand behavior, and receive a deterministic office-contact reply from `modules/localized_replies.py` instead of the normal grievance acknowledgment. Also updated the API “other” bucket contract to include `Personal Request` and added focused classifier/end-to-end regressions for land-dispute and transfer examples.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `sansadx_backend/ai_engine.py`, `modules/localized_replies.py`, `main.py`, `api_router.py`, `tests/test_unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `tests/test_e2e_core_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The detector is intentionally narrow so generic public complaints are not accidentally downgraded into office-favor requests. If future examples are missed, extend the marker list with similarly explicit first-person/discretionary phrases rather than broadening around generic words like `help` or `dispute`.

- Date: 2026-06-05
- Request: Push the emergency no-ack classification tightening to GitHub for deployment.
- Summary: Pushed commit `ba0a2787` (`Tighten emergency no-ack classification`) to `origin/main`, publishing the stronger emergency rescue/classification layer plus the Indic-safe emergency keyword detection that suppresses citizen acknowledgements for severe law-and-order, women/child danger, health-emergency, disaster, and suicide-risk reports.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This release affects backend intake behavior, so live verification should focus on the EC2 backend commit, health endpoint, and emergency-message flows rather than frontend assets.

- Date: 2026-06-05
- Request: Tighten emergency classification so disaster, riot, women/child danger, health emergency, and suicide-risk messages do not send a WhatsApp acknowledgement.
- Summary: Expanded the high-confidence taxonomy rescue layer to recognize explicit emergency patterns across disaster, law-and-order violence, women/child danger, health emergency, and suicide-risk reports, then forced those cases into the emergency path in `ai_engine.py` even when the model guessed a normal civic category. Also fixed `modules/emergency_keywords.py` normalization so Indic-script terms like `दंगा` survive keyword detection, which restores the existing no-ack emergency behavior for Hindi and other regional-language reports. Added focused unit and end-to-end regressions proving that a Hindi riot message is saved as an emergency case and sends no citizen acknowledgement even if the AI originally misclassifies it.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `sansadx_backend/ai_engine.py`, `modules/emergency_keywords.py`, `tests/test_unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `tests/test_e2e_core_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The emergency rescue layer is intentionally explicit rather than fuzzy so ordinary complaints do not lose acknowledgements by accident. If future misses still appear, add narrow markers/tests for that emergency class instead of weakening the boundary between emergency and routine civic complaints.

- Date: 2026-06-05
- Request: Make manual geography saves teach future resolver matches by using aliases first.
- Summary: Updated the resolver so tenant manual aliases are evaluated before core geography using exact/boundary/spaceless alias-form matching instead of a crude substring shortcut. Also changed Briefcase manual geography saves to persist a reusable `geo_manual_override` row whenever an operator saves a real location+assembly, so a correction like `Teacher Colony -> Belgaum South` fixes future cases instead of only the current one. Added a regression proving the case save creates the alias and that a later `Teacher Colony...` message resolves through the alias-first path.
- Files touched: `modules/geography_resolver.py`, `api_router.py`, `tests/test_briefcase_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This intentionally makes case-screen manual geography more powerful. If operators later want case-only saves sometimes, the next refinement should be an explicit UI choice rather than silently weakening alias-first precedence again.

- Date: 2026-06-05
- Request: Push the alias-first reusable Briefcase geography fix to GitHub for deployment.
- Summary: Pushed commit `84f0e068` (`Teach reusable geography aliases from Briefcase`) to `origin/main`, publishing the alias-first resolver behavior plus the case-save path that writes tenant-scoped reusable `geo_manual_override` rows for future matching.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The live change depends on the backend EC2 deploy finishing on this new commit. This release intentionally leaves unrelated local edits in `data/geography/Ghaziabad/Loni.json` and `tenant_overrides.json` unpushed.

- Date: 2026-06-05
- Request: Fix the Briefcase delete button not working for primary accounts.
- Summary: Updated Briefcase soft-delete backend permissions so `owner` accounts now share the same delete, deleted-list, and restore access as legacy `mp`/`admin` primary accounts and `pr` users. Added a focused regression proving the full owner delete-view-restore flow, which closes the role-migration gap that was making the frontend delete button fail with a backend 403 for owner tenants.
- Files touched: `api_router.py`, `tests/test_briefcase_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This fixes the likely root cause for the broken delete action. If operators still report a dead-feeling button after deploy, the next pass should surface the single-delete API failure as a visible toast in `BriefcaseCasesTable.jsx` instead of only logging to the console.

- Date: 2026-06-05
- Request: Push the Briefcase delete permission fix to GitHub for deployment.
- Summary: Pushed commit `850f4f58` (`Fix Briefcase owner delete access`) to `origin/main`, publishing the backend permission fix that restores Briefcase delete, deleted-list, and restore access for `owner` accounts while preserving the existing staff restriction.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The backend deploy still needs to finish on AWS EC2 before the live app reflects this change. If the button still appears dead after deploy, the next likely improvement is a visible single-delete failure toast in the Briefcase table UI.

- Date: 2026-06-05
- Request: Push the generic-token scorer hardening fix to GitHub for deployment.
- Summary: Pushed commit `7c436111` (`Harden generic locality scoring`) to `origin/main`, publishing the resolver guard that prevents multi-word sub-locality candidates from winning on generic container overlap alone, which specifically blocks `Teacher Colony` from drifting into unrelated `... Colony ...` localities.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy intentionally prefers unresolved over wrong when only generic overlap exists. If any live locality still misses after this, the follow-up should be better shared geography or an explicit manual correction, not relaxing the generic-token guard.

- Date: 2026-06-05
- Request: Stop the shared geography scorer from still mapping `Teacher Colony` to `Kariyappa Colony` after alias/override cleanup.
- Summary: Hardened `modules/geography_resolver.py` so multi-word sub-locality candidates must share at least one meaningful non-generic token with the user message before they can win. This blocks false positives driven only by generic container words like `colony` while preserving valid parent/sub-locality matches such as `Teachers Colony - Khasbag`. Added a focused regression with `Kariyappa Colony Tilakwadi` present in the same seat and verified with `venv/bin/python -m pytest tests/test_geography_resolver.py tests/test_ai_location_grounding.py -q` plus `venv/bin/python -m py_compile modules/geography_resolver.py`.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This intentionally prefers unresolved over wrong when only generic overlap exists. If a future real constituency depends on a generic-only multi-word match, that locality should be expressed through cleaner shared geography or a manual correction rather than weakening the scorer again.

- Date: 2026-06-05
- Request: Push the legacy generated geography-override cleanup path to GitHub for deployment.
- Summary: Pushed commit `ff9d6ee6` (`Clean legacy generated geography overrides`) to `origin/main`, publishing the startup/admin cleanup path that deletes stale generated `geo_override` rows when the same tenant/key already exists as a generated `geo_alias`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy finally applies the DB cleanup on live startup/regeneration, but it remains intentionally conservative and will not delete older standalone legacy `geo_override` rows that are not mirrored by a generated alias.

- Date: 2026-06-05
- Request: Add a one-time cleanup path that actually removes stale legacy generated `geo_override` rows from live data.
- Summary: Added `cleanup_legacy_generated_geo_overrides()` to delete `geo_override` rows when the same tenant/key already exists as a generated `geo_alias`, then wired that cleanup into both startup geography sync and admin-triggered geography regeneration. Added a regression proving the cleanup deletes only the stale generated-collision rows and preserves manual-only rows. Verified with `venv/bin/python -m pytest tests/test_override_persistence.py tests/test_same_seat_isolation.py tests/test_geography_onboarding_api.py -q` and `venv/bin/python -m py_compile sansadx_backend/db.py modules/geography_resolver.py admin_api.py main.py`.
- Files touched: `sansadx_backend/db.py`, `admin_api.py`, `main.py`, `tests/test_override_persistence.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The deploy-time cleanup is intentionally conservative: it only deletes legacy `geo_override` rows when a generated alias for the same tenant/key already exists. Older manual corrections still stored as legacy `geo_override` but not mirrored by aliases are preserved until operators resave them through the workspace.

- Date: 2026-06-05
- Request: Push the geography architecture simplification fix to GitHub for deployment.
- Summary: Pushed commit `7d3751b2` (`Separate manual and generated geography overrides`) to `origin/main`, publishing the runtime split where generated geography now writes only `geo_alias` helpers, manual corrections persist separately, and the resolver no longer lets generated override rows outrank the shared seat-geometry matching model.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy fixes the backend precedence problem, but older tenants should still be reviewed over time so meaningful legacy `geo_override` rows are re-saved through the admin workspace into the new manual-correction path.

- Date: 2026-06-05
- Request: Simplify the geography architecture so generated geography stops acting like a forced override layer, while keeping manual corrections simple for operators.
- Summary: Split runtime geography behavior into generated `geo_alias` helpers versus manual corrections. Updated DB override helpers so admin-managed corrections now persist as `geo_manual_override`, legacy `geo_override` rows are only treated as manual when they do not collide with a generated alias, and `auto_generate_overrides()` now writes only `geo_alias` rows instead of regenerating forced `geo_override` rows. Added regressions for the migration/filtering behavior and updated same-seat/onboarding expectations. Verified with `venv/bin/python -m pytest tests/test_override_persistence.py tests/test_same_seat_isolation.py tests/test_geography_onboarding_api.py -q`, `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx`, and `venv/bin/python -m py_compile sansadx_backend/db.py modules/geography_resolver.py admin_api.py`.
- Files touched: `sansadx_backend/db.py`, `modules/geography_resolver.py`, `tests/test_override_persistence.py`, `tests/test_same_seat_isolation.py`, `tests/test_geography_onboarding_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This fixes the runtime precedence issue without forcing operators into a new workflow, but older tenants with meaningful legacy `geo_override` rows should still be reviewed and resaved through the admin workspace over time so everything migrates cleanly into `geo_manual_override`.

- Date: 2026-06-05
- Request: Push the spreadsheet-style bulk correction parser update to GitHub for deployment.
- Summary: Pushed commit `3d1c223d` (`Accept spreadsheet bulk corrections`) to `origin/main`, publishing tab-separated bulk manual-correction import alongside the existing `alias => assembly` format in the Shared Geography workspace.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy changes only the admin workflow. The parser still stays intentionally strict and line-based so malformed spreadsheet rows fail loudly instead of saving partial garbage.

- Date: 2026-06-05
- Request: Make bulk manual-correction import accept spreadsheet-style pasted rows.
- Summary: Extended the Shared Geography bulk manual-correction parser so it now accepts either `alias => assembly` or two tab-separated columns copied directly from a spreadsheet, and updated the inline help/error copy accordingly. Verified with `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx` and `PATH=/opt/homebrew/bin:$PATH npm run build --prefix admin`.
- Files touched: `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The parser still intentionally rejects malformed lines one-by-one; if operators later want CSV upload, that should be added explicitly rather than inferring too many loose delimiters.

- Date: 2026-06-04
- Request: Push the bulk manual-correction controls to GitHub for deployment.
- Summary: Pushed commit `7bc4f400` (`Add bulk manual correction controls`) to `origin/main`, publishing `Bulk Add` and confirmation-gated `Delete All` actions for tenant-specific manual geography corrections inside the unified Shared Geography workspace.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy changes only the admin workflow. Bulk parsing intentionally remains strict (`alias => assembly`) so malformed pasted rows do not silently save.

- Date: 2026-06-04
- Request: Add `Bulk Add` and `Delete All` actions to Manual Matching Corrections in the unified Shared Geography workspace.
- Summary: Added a bulk-entry mode for tenant-specific manual geography corrections using one line per rule in the format `alias => assembly`, plus a confirmation-gated `Delete All` action that clears every manual correction for the current tenant. Kept the existing in-place edit flow and persisted everything through the same `geo_override` compatibility path. Verified with `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx` and `PATH=/opt/homebrew/bin:$PATH npm run build --prefix admin`.
- Files touched: `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Bulk parsing intentionally stays strict to avoid malformed saves; if operators later need CSV upload or smarter validation, that should be added as a second bulk-import mode rather than weakening the simple `alias => assembly` contract.

- Date: 2026-06-04
- Request: Push the manual-correction edit action upgrade to GitHub for deployment.
- Summary: Pushed commit `09d386f8` (`Add manual correction edit actions`) to `origin/main`, publishing in-place `Edit`, `Update Correction`, and `Cancel` actions for tenant-specific manual geography corrections inside the unified Shared Geography workspace.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy changes only the admin interaction flow; the backend storage model remains the same `geo_override` compatibility path under the hood until a deeper geography-model migration happens later.

- Date: 2026-06-04
- Request: Add an edit action to Manual Matching Corrections in the unified Shared Geography workspace.
- Summary: Added in-place edit support for tenant-specific manual geography corrections inside `GeographyWorkspacePage.jsx`, including `Edit`, `Update Correction`, and `Cancel` flows that reuse the existing `geo_override` persistence path without forcing operators to delete and recreate a correction. Also extended the admin geography test to assert the new edit affordance. Verified with `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx` and `PATH=/opt/homebrew/bin:$PATH npm run build --prefix admin`.
- Files touched: `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This stays UI-only and keeps the same backend storage. A later deeper migration can still move manual corrections into a richer canonical locality model without changing this operator interaction pattern.

- Date: 2026-06-04
- Request: Push the Shared Geography workflow unification pass to GitHub for deployment.
- Summary: Pushed commit `b1115e45` (`Unify shared geography workspace flow`) to `origin/main`, publishing the tenant-aware workspace as the single operator surface for shared seat geography, manual matching corrections, and resolver alias diagnostics while the old rules route now redirects back into the workspace.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This deploy unifies the admin experience first, but the backend still stores manual corrections as `geo_override` under the hood for compatibility. A later migration can simplify that storage model without changing the operator workflow again.

- Date: 2026-06-04
- Request: Start unifying shared geography so upload, manual corrections, and resolver cleanup behave like one operator workflow while preserving the parent/sub-locality model.
- Summary: Folded tenant-specific `geo_override` management into the tenant-aware Shared Geography workspace as `Manual Matching Corrections`, added explanatory copy that separates shared seat geography from manual corrections and generated resolver aliases, updated the Shared Geography landing page to point operators to the workspace instead of a separate rules tool, and converted `/dashboard/shared-geography/rules` into a compatibility redirect back to the workspace. Verified with `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx` and `PATH=/opt/homebrew/bin:$PATH npm run build --prefix admin`.
- Files touched: `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `admin/app/dashboard/shared-geography/rules/page.js`, `admin/app/dashboard/shared-geography/page.js`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This unifies the operator experience first, but `geo_override` still exists under the hood for backward-compatible routing. A later migration can move those manual corrections into a richer canonical locality model without changing the workspace contract again.

- Date: 2026-06-04
- Request: Push the Shared Geography workspace tenant-picker discoverability fix to GitHub for deployment.
- Summary: Pushed commit `ca460252` (`Expose tenant alias cleanup workspace`) to `origin/main`, publishing the generic Shared Geography tenant picker/jump flow that surfaces the tenant-scoped `geo_alias` cleanup tools without requiring operators to guess the `tenant_id` URL contract.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The new picker improves discoverability, but the actual alias data still depends on valid tenant context and the admin frontend deployment finishing successfully after the `main` push.

- Date: 2026-06-04
- Request: Make the Shared Geography workspace expose the tenant-scoped alias cleanup flow instead of hiding it behind an undocumented `tenant_id` query parameter.
- Summary: Added a tenant picker notice to the generic Shared Geography workspace so operators can jump directly into tenant-aware alias cleanup mode, then tightened the admin page test harness to mock `useRouter`/`/api/admin/mps` and added coverage for that navigation flow. Also fixed the new picker label association for accessibility and testability. Verified with `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx`.
- Files touched: `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This improves discoverability only. Operators still need a valid `tenant_id` context to inspect actual `geo_alias` rows, and the page could later benefit from a richer tenant search or a dedicated tenant selector route if the account list grows large.

- Date: 2026-06-04
- Request: Push the admin `geo_alias` inspection/deletion tool to GitHub for deployment.
- Summary: Pushed commit `df13e59c` (`Add admin geo alias cleanup tool`) to `origin/main`, publishing the Shared Geography admin panel for tenant resolver aliases plus the supporting admin API list/delete endpoints.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Production still depends on both the backend EC2 deploy workflow and the admin frontend deployment finishing successfully after this `main` push.

- Date: 2026-06-04
- Request: Push the admin `geo_alias` inspection/deletion tool to GitHub for deployment.
- Summary: Pending push from `main` for the Shared Geography admin tooling that lists and deletes tenant-scoped `geo_alias` rows through new admin API endpoints and a tenant-aware `Resolver Aliases` panel. This release intentionally excludes the unrelated local `tenant_overrides.json` changes.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The live behavior depends on both the backend EC2 deploy workflow and the admin frontend deploy picking up this `main` push, since the feature spans `admin_api.py` and the Next.js admin workspace UI.

- Date: 2026-06-04
- Request: Build an admin tool to inspect and delete tenant `geo_alias` rows.
- Summary: Added admin API endpoints to list and delete tenant-scoped `geo_alias` rows by id, then wired a new `Resolver Aliases` panel into the tenant-aware Shared Geography workspace so operators can inspect poisoned aliases and remove them safely. Also added backend regressions for alias list/delete and refreshed the geography workspace frontend test. Verified with `venv/bin/python -m pytest tests/test_geography_onboarding_api.py -q` and `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx`.
- Files touched: `admin_api.py`, `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `tests/test_geography_onboarding_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Deleting a generated alias is immediate for tenant-scoped resolver lookups, but the alias may return after future geography regeneration until the underlying alias-generation rules or geography data are corrected.

- Date: 2026-06-04
- Request: Push the AI-hint geography cleanup to GitHub for deployment.
- Summary: Pushed commit `9c7d78f1` (`Unify AI geography hint resolution`) to `origin/main`, publishing the removal of the legacy classifier-side geography matcher so AI-extracted locations now go back through the shared resolver before they can save location or assembly.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Production still depends on the backend EC2 deploy workflow completing successfully after this `main` push.

- Date: 2026-06-04
- Request: Push the AI-hint geography cleanup to GitHub for deployment.
- Summary: Pending push from `main` for the `ai_engine.py` cleanup that removes the legacy parallel geography matcher and forces AI-extracted locations back through the shared resolver. This release intentionally excludes the unrelated local `tenant_overrides.json` changes.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The live behavior depends on the backend EC2 deploy workflow completing after the `main` push, since this change affects backend case classification and geography persistence.

- Date: 2026-06-04
- Request: Stop the AI classifier from writing wrong geography through a legacy parallel matcher after the shared resolver was fixed.
- Summary: Removed the duplicate location-matching path from `sansadx_backend/ai_engine.py` that had been scanning raw geography rows and override maps independently of the shared resolver. AI-extracted locations are now treated only as hints and must be re-resolved through `modules/geography_resolver.py` before they can populate `grievance_data.location` or `assembly_constituency`. Added a regression for the `Teacher Colony ... neer illa` shape where message-level grounding misses but the shared resolver can still safely resolve the AI hint. Verified with `venv/bin/python -m pytest tests/test_ai_location_grounding.py -q` and `venv/bin/python -m pytest tests/test_whatsapp_geography_decision.py -q`.
- Files touched: `sansadx_backend/ai_engine.py`, `tests/test_ai_location_grounding.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This removes classifier-time custom geography guessing on purpose. If any tenant depended on that older parallel matcher, the correct follow-up is to strengthen the shared resolver or shared aliases rather than reintroduce a second geography engine.

- Date: 2026-06-04
- Request: Push the parent-row geography resolver fix to GitHub for deployment.
- Summary: Pushed commit `28ba5125` (`Prefer explicit parent locality rows`) to `origin/main`, publishing the seat-generic resolver behavior where explicit standalone parent rows beat inherited parent aliases from sub-locality rows while preserving `sub only` and `parent + sub` matching.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Production still depends on the backend EC2 deploy workflow completing successfully after this `main` push.

- Date: 2026-06-04
- Request: Push the parent-row geography resolver fix to GitHub for deployment.
- Summary: Pending push from `main` for the standalone parent-locality preference fix in the shared geography resolver. This release intentionally excludes the unrelated local `tenant_overrides.json` changes.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The live behavior depends on the backend EC2 deploy workflow completing after the `main` push, since this change is entirely in backend geography resolution.

- Date: 2026-06-04
- Request: Make geography resolution honor standalone parent-locality rows alongside `sub-locality - parent locality` rows so parent-only mentions resolve correctly.
- Summary: Tightened `modules/geography_resolver.py` so parent-only matches from an explicitly saved parent row now outrank parent aliases inherited from sub-locality rows. This preserves the intended data model where a seat can store `Shahapur` on its own plus rows like `Navi Galli - Shahapur`, and citizens can mention only the parent, only the sub-locality, or both. Added focused regressions for explicit parent-row preference plus `sub only` and `sub + parent` matching on the same seat-scoped geography data. Verified with `venv/bin/python -m pytest tests/test_geography_resolver.py -q` and `venv/bin/python -m pytest tests/test_ai_location_grounding.py -q`.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This stays seat-generic and does not hardcode Shahapur/Khasbag. If live operators still see blanks after this, the next step should be reading `case_metadata.geography_diagnostics` on an affected case to see whether the miss is happening before candidate ranking or during tenant-scope filtering.

- Date: 2026-06-04
- Request: Make geography matching seat-generic and robust when citizens mention only the parent locality, only the sub-locality, or both, including noisy variants.
- Summary: Extended `modules/geography_resolver.py` so hyphen-delimited seat geography rows like `Teachers Colony - Khasbag` are parsed into structured `sub_locality + parent_locality` at save/index time instead of being treated as one raw string. Alias generation is now seat-scoped and supports parent-only, sub-only, and combined mentions, plus light structured phrase variants for generic Indian-language/operator mistakes, while keeping those variants out of canonical display inference so stored names remain stable. Added focused resolver regressions for sub-only, parent+sub, and parent-only resolution using the same seat data. Verified with `venv/bin/python -m pytest tests/test_geography_resolver.py -q` and `venv/bin/python -m pytest tests/test_ai_location_grounding.py -q`.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is still intentionally seat-scoped and ambiguity-safe. If live seats have duplicate sub-locality names across parents/assemblies, the next hardening step should be surfacing those ambiguity candidates in ops UI rather than guessing through them.

- Date: 2026-06-04
- Request: Push the seat-generic parent/sub-locality geography resolver upgrade to GitHub for deployment.
- Summary: Pending push from `main` for the structured `X - Parent` locality parsing and seat-scoped alias expansion fix. This release intentionally excludes the unrelated local `tenant_overrides.json` changes.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The live fix depends on the backend EC2 deploy workflow completing after the `main` push, since this changes the backend geography resolver.

- Date: 2026-06-04
- Request: Fix wrong grievance routing where `Teacher Colony nalli 3 din neer illa` was classified as `Teacher Availability` instead of a water-supply issue.
- Summary: Hardened taxonomy rescue logic in `sansadx_backend/unified_taxonomy.py` so obvious water-outage language (`water/paani/neer/neeru` plus outage cues like `illa`, `bandilla`, `nahi`, `not coming`) now forces `Infrastructure & Utilities -> Water Supply` even if the upstream model guessed an education label due to locality names like `Teacher Colony`. Also added Kannada/Hinglish water markers and focused regressions proving both `build_taxonomy_fields()` and `_normalize_grievance_taxonomy()` rescue the screenshot case correctly. Verified with `venv/bin/python -m pytest tests/test_ai_location_grounding.py -q`.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This rescue path is intentionally narrow and should stay structural. If similar false positives appear for other locality-name patterns (`Doctor Layout`, `Police Quarters`, etc.), extend the location-aware signal cleanup carefully rather than adding constituency-specific special cases.

- Date: 2026-06-04
- Request: Push the water-outage taxonomy rescue fix to GitHub for deployment.
- Summary: Pending push from `main` for the `Teacher Colony ... neer illa` classification fix. This release intentionally excludes the unrelated local `tenant_overrides.json` changes.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The live fix depends on the backend EC2 deploy workflow completing after the `main` push, since this is a backend taxonomy change.

- Date: 2026-06-03
- Request: Add an internal English-support fallback for media/voice-note geography mapping without making translation the primary source of truth.
- Summary: Extended voice-note and media normalization to emit `english_support_text`, threaded that support text through inbound WhatsApp media handling, and taught `finalize_geography_decision()` to attempt a second geography resolver pass from the English support text only when the original-language pass fails. Added focused regressions proving voice-note/media normalization returns the new field and that geography diagnostics record when an `english_support` fallback resolved the location.
- Files touched: `modules/voice_note_normalizer.py`, `modules/whatsapp_media_intake.py`, `modules/whatsapp_geography.py`, `main.py`, `tests/test_voice_note_normalizer.py`, `tests/test_whatsapp_media_intake.py`, `tests/test_whatsapp_geography_decision.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This currently strengthens the media/voice-note path, which is where the most severe native-script ASR misses are happening. If we later want the same dual-pass approach for plain text complaints, we should add it through a similarly explicit support-text contract rather than silently translating all text before geography mapping.

- Date: 2026-06-03
- Request: Push the dual-pass voice/media geography fallback update to GitHub for deployment.
- Summary: Pushed commit `d4e9ed4b` (`Add dual-pass voice geography fallback`) to `origin/main`, publishing the original-language-first plus English-support fallback resolver path for media/voice-note geography handling.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a backend-affecting change, so production depends on the backend deploy workflow completing successfully after the `main` push.

- Date: 2026-06-03
- Request: Finish the admin IA migration by extracting the remaining legacy-owned pages into shared domain modules and converting the old top-level routes into real redirects.
- Summary: Completed the migration spine by moving `Staff Management`, `Audit Log`, `Case Intelligence`, `Knowledge Sync`, `Intelligence Engine`, and `Parliament Sync` into shared modules under `admin/components/admin-domains/...`, wiring the new domain routes to those modules, and converting the old tool-shaped top-level routes into actual redirects to the new canonical homes. Also updated the remaining tests and internal imports to use the domain routes/shared modules. Verified with `npm run test --prefix admin -- --run tests/dashboard.test.jsx tests/geography.test.jsx tests/health-analytics.test.jsx tests/login.test.jsx tests/seat-maps.test.jsx tests/setup-checklist.test.jsx`.
- Files touched: `admin/components/admin-domains/staff-access/StaffManagementPage.jsx`, `admin/components/admin-domains/staff-access/AuditLogPage.jsx`, `admin/components/admin-domains/cases-intelligence/CaseIntelligencePage.jsx`, `admin/components/admin-domains/cases-intelligence/KnowledgeSyncPage.jsx`, `admin/components/admin-domains/cases-intelligence/IntelligenceEnginePage.jsx`, `admin/components/admin-domains/system/ParliamentSyncPage.jsx`, `admin/app/dashboard/staff-access/users/page.js`, `admin/app/dashboard/staff-access/audit/page.js`, `admin/app/dashboard/cases-intelligence/explorer/page.js`, `admin/app/dashboard/cases-intelligence/knowledge/page.js`, `admin/app/dashboard/cases-intelligence/engine/page.js`, `admin/app/dashboard/system/parliament-sync/page.js`, `admin/app/dashboard/staff/page.js`, `admin/app/dashboard/audit/page.js`, `admin/app/dashboard/intelligence/page.js`, `admin/app/dashboard/knowledge/page.js`, `admin/app/dashboard/brain/page.js`, `admin/app/dashboard/parliament-sync/page.js`, `admin/app/dashboard/profiles/page.js`, `admin/app/dashboard/geography/page.js`, `admin/app/dashboard/rules/page.js`, `admin/app/dashboard/mps/new/page.js`, `admin/app/dashboard/health/page.js`, `admin/app/dashboard/announcements/page.js`, `admin/app/dashboard/settings/page.js`, `admin/app/dashboard/analytics/page.js`, `admin/components/admin-domains/cases-intelligence/KnowledgeSyncPage.jsx`, `admin/tests/geography.test.jsx`, `admin/tests/health-analytics.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The admin IA is now structurally coherent, but the sidebar still intentionally exposes a `Legacy Tools` group for operational continuity. A later cleanup phase can remove or reduce that group once you’re comfortable with the new domain homes and any bookmarked old URLs have had time to settle.

- Date: 2026-06-03
- Request: Continue the admin IA migration by moving smaller System and Cases & Intelligence screens into shared domain ownership.
- Summary: Moved `Tenant Health`, `Announcements`, `Settings`, and `Usage Analytics` into shared domain modules under `admin/components/admin-domains/system/` and `admin/components/admin-domains/cases-intelligence/`. Both the new routes (`/dashboard/system/health`, `/dashboard/system/announcements`, `/dashboard/system/settings`, `/dashboard/cases-intelligence/analytics`) and the old top-level compatibility routes now import the same shared modules. Verified with `npm run test --prefix admin -- --run tests/dashboard.test.jsx tests/geography.test.jsx tests/health-analytics.test.jsx tests/login.test.jsx tests/seat-maps.test.jsx tests/setup-checklist.test.jsx`.
- Files touched: `admin/components/admin-domains/system/TenantHealthPage.jsx`, `admin/components/admin-domains/system/AnnouncementsPage.jsx`, `admin/components/admin-domains/system/SystemSettingsPage.jsx`, `admin/components/admin-domains/cases-intelligence/UsageAnalyticsPage.jsx`, `admin/app/dashboard/health/page.js`, `admin/app/dashboard/announcements/page.js`, `admin/app/dashboard/settings/page.js`, `admin/app/dashboard/analytics/page.js`, `admin/app/dashboard/system/health/page.js`, `admin/app/dashboard/system/announcements/page.js`, `admin/app/dashboard/system/settings/page.js`, `admin/app/dashboard/cases-intelligence/analytics/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The largest admin pages (`brain`, `intelligence`, `knowledge`, `parliament-sync`) still live in their old route files. The next extraction phase should decide whether to continue ownership migration there or start converting the already-extracted legacy routes into full redirects.

- Date: 2026-06-03
- Request: Continue the admin IA migration by moving the heavier Accounts and Shared Geography screens into the new domain ownership model.
- Summary: Moved the real implementations for the old `profiles` and `geography` pages into shared domain modules (`admin/components/admin-domains/accounts/ProfileEditorPage.jsx` and `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`). The new routes (`/dashboard/accounts/registry`, `/dashboard/shared-geography/workspace`) now import those modules directly, while the old `/dashboard/profiles` and `/dashboard/geography` routes are compatibility wrappers only. Verified with `npm run test --prefix admin -- --run tests/dashboard.test.jsx tests/geography.test.jsx tests/health-analytics.test.jsx tests/login.test.jsx tests/seat-maps.test.jsx tests/setup-checklist.test.jsx`.
- Files touched: `admin/components/admin-domains/accounts/ProfileEditorPage.jsx`, `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `admin/app/dashboard/accounts/registry/page.js`, `admin/app/dashboard/shared-geography/workspace/page.js`, `admin/app/dashboard/profiles/page.js`, `admin/app/dashboard/geography/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Old route compatibility is still preserved intentionally. The next migration slice should decide which legacy routes can now become redirects, and whether `Seat Maps`, `Cases & Intelligence`, and `System` need the same shared-module ownership treatment before we simplify the sidebar further.

- Date: 2026-06-03
- Request: Move actual admin page ownership into the new domain routes instead of only bridging with re-export placeholders.
- Summary: Extracted the first two real admin screens into shared domain modules: account creation now lives in `admin/components/admin-domains/accounts/CreateAccountPage.jsx`, and geography rules now live in `admin/components/admin-domains/shared-geography/GeographyRulesPage.jsx`. Both the new domain routes (`/dashboard/accounts/new`, `/dashboard/shared-geography/rules`) and the old compatibility routes (`/dashboard/mps/new`, `/dashboard/rules`) now import those shared modules, so ownership has started shifting into the new IA without breaking existing URLs. Verified with `npm run test --prefix admin -- --run tests/dashboard.test.jsx tests/geography.test.jsx tests/health-analytics.test.jsx tests/login.test.jsx tests/seat-maps.test.jsx tests/setup-checklist.test.jsx`.
- Files touched: `admin/components/admin-domains/accounts/CreateAccountPage.jsx`, `admin/components/admin-domains/shared-geography/GeographyRulesPage.jsx`, `admin/app/dashboard/accounts/new/page.js`, `admin/app/dashboard/shared-geography/rules/page.js`, `admin/app/dashboard/mps/new/page.js`, `admin/app/dashboard/rules/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The heavier `accounts/registry` and `shared-geography/workspace` screens still live in their old modules. The next ownership slice should extract those larger screens similarly, then start deciding which old routes can become full redirects instead of compatibility wrappers.

- Date: 2026-06-03
- Request: Wire real redirects/migrations from the old admin top-level tools into the new domain-first architecture and test the result.
- Summary: Added concrete subroutes under the new admin domains that reuse the existing page implementations (`/dashboard/accounts/registry`, `/dashboard/accounts/new`, `/dashboard/shared-geography/workspace`, `/dashboard/shared-geography/rules`, `/dashboard/cases-intelligence/*`, `/dashboard/staff-access/*`, `/dashboard/system/*`) and repointed active workflow CTAs and cross-links in Overview, tenant setup, Knowledge, and Seat Maps to those domain routes. Verified with `npm run test --prefix admin -- --run tests/dashboard.test.jsx tests/geography.test.jsx tests/health-analytics.test.jsx tests/login.test.jsx tests/seat-maps.test.jsx tests/setup-checklist.test.jsx` using the Homebrew Node/npm path.
- Files touched: `admin/app/dashboard/accounts/page.js`, `admin/app/dashboard/accounts/registry/page.js`, `admin/app/dashboard/accounts/new/page.js`, `admin/app/dashboard/shared-geography/page.js`, `admin/app/dashboard/shared-geography/workspace/page.js`, `admin/app/dashboard/shared-geography/rules/page.js`, `admin/app/dashboard/cases-intelligence/page.js`, `admin/app/dashboard/cases-intelligence/explorer/page.js`, `admin/app/dashboard/cases-intelligence/knowledge/page.js`, `admin/app/dashboard/cases-intelligence/engine/page.js`, `admin/app/dashboard/cases-intelligence/analytics/page.js`, `admin/app/dashboard/staff-access/page.js`, `admin/app/dashboard/staff-access/users/page.js`, `admin/app/dashboard/staff-access/audit/page.js`, `admin/app/dashboard/system/page.js`, `admin/app/dashboard/system/health/page.js`, `admin/app/dashboard/system/announcements/page.js`, `admin/app/dashboard/system/settings/page.js`, `admin/app/dashboard/system/parliament-sync/page.js`, `admin/app/dashboard/page.js`, `admin/app/dashboard/mps/[tenant_id]/setup/page.js`, `admin/app/dashboard/knowledge/page.js`, `admin/app/dashboard/seat-maps/page.js`, `admin/tests/setup-checklist.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This still preserves the old top-level routes, so the migration is only partial by design. The next phase should decide which legacy routes to formally redirect, which page titles/descriptions need to be domain-aware, and how to move real ownership from old modules into the new route homes.

- Date: 2026-06-03
- Request: Start building the new admin frontend architecture around a domain-first IA instead of the older page-by-page tool layout.
- Summary: Added the first non-destructive admin IA slice by replacing the sidebar's primary navigation with the new domain homes (`Accounts`, `Seats`, `Shared Geography`, `Seat Maps`, `Cases & Intelligence`, `Staff & Access`, `System`), updating dashboard route-title mapping to recognize those domains, and creating new top-level shell pages that bridge operators into the still-live legacy tools while migration continues underneath.
- Files touched: `admin/components/Sidebar.js`, `admin/app/dashboard/layout.js`, `admin/app/dashboard/accounts/page.js`, `admin/app/dashboard/seats/page.js`, `admin/app/dashboard/shared-geography/page.js`, `admin/app/dashboard/cases-intelligence/page.js`, `admin/app/dashboard/staff-access/page.js`, `admin/app/dashboard/system/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is only the IA foundation. The old pages still exist and remain the live tools underneath. Next phases should migrate real page ownership into these domains, add redirects where appropriate, and eventually retire the legacy top-level page concepts instead of keeping both forever.

- Date: 2026-06-03
- Request: Make seat-generic, tenant-safe architecture an explicit standing rule in project memory for all future work.
- Summary: Added a top-level operating rule to `PROJECT_MEMORY.md` stating that every new change should default to seat-generic, tenant-safe architecture and should not hardcode behavior to one constituency or one tenant except as a clearly isolated, documented bootstrap fallback.
- Files touched: `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is a process hardening change only; the practical follow-up is to keep checking new geography, map, dashboard, and admin work against this rule before implementation.

- Date: 2026-06-03
- Request: Make geography matching understand both parent localities and sub-localities from shared geography uploads so complaints can resolve correctly whether citizens mention `Shahapur` or a more specific place like `Teli Patil Galli Shahapur`.
- Summary: Added hierarchy-aware locality parsing inside `modules/geography_resolver.py`, so uploaded geography rows can now infer `sub_locality`, `parent_locality`, and `hierarchy_type` during sanitation/indexing without changing the stored raw `locality` contract. Resolver ranking now prefers specific sub-locality matches, returns richer metadata (`matched_type`, `parent_locality`), and keeps broad parent-locality fallback intact. Also preserved the older Marathi `Vadagaon` voice-drift behavior after tightening the hierarchy logic. Verified with `venv/bin/python -m pytest tests/test_geography_resolver.py -q` and `venv/bin/python -m py_compile modules/geography_resolver.py`.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Parent/sub-locality inference is intentionally conservative and currently driven by repeated suffix patterns inside the same seat/assembly data. If admins later want explicit hierarchy editing in the geography UI, we should surface `parent_locality` and `sub_locality` there instead of relying only on inference.

- Date: 2026-06-03
- Request: Push the hierarchical geography matching update to GitHub.
- Summary: Pushed commit `ee373e9c` (`Add hierarchical geography matching`) to `origin/main`, publishing parent/sub-locality inference for shared geography uploads plus richer resolver metadata (`matched_type`, `parent_locality`) while preserving the older voice-drift matches.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy before live ingestion and dashboard geography begin using the hierarchical resolver behavior.

- Date: 2026-06-03
- Request: Fix the Briefcase right-side case detail so the green AI header appears again and the summary stops repeating the raw message.
- Summary: Updated the Briefcase drawer to derive its suggestion banner from canonical case taxonomy fields when `case_metadata.ai_*` is missing, hide AI confidence in the UI, and use a structured fallback summary when the stored summary is empty or just duplicates the raw citizen message. Also updated `main.py` so newly enriched cases persist `ai_category`, `ai_subcategory`, `ai_confidence`, and a better fallback summary in `case_metadata`. Verified backend syntax with `venv/bin/python -m py_compile main.py`; frontend build/test verification was not possible in this shell because `node`/`npm` are unavailable here.
- Files touched: `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `main.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Existing cases will benefit from the new frontend fallbacks immediately, but only newly enriched or re-enriched cases will permanently carry the richer `case_metadata.ai_*` fields unless we run a backfill later.

- Date: 2026-06-03
- Request: Push the Briefcase AI drawer summary/header fallback fix to GitHub.
- Summary: Pushed commit `d3ff71a5` (`Fix Briefcase AI drawer summary fallbacks`) to `origin/main`, publishing the drawer-side AI category/summary fallbacks and the backend `case_metadata` persistence of `ai_category`, `ai_subcategory`, `ai_confidence`, and improved summaries for future cases.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Frontend changes depend on Vercel deploy, and backend persistence changes still need an EC2 deploy before new incoming cases start saving the richer metadata in production.

- Date: 2026-06-02
- Request: Remove the large blank space under the 10-row grievance queue and make the desktop right column match the left queue height.
- Summary: Synced the desktop dashboard right-side `Workload + Constituency map` stack to the measured height of the 10-row grievance queue using a client-side `ResizeObserver`, anchored the left queue card to its content height instead of allowing grid stretch to create dead space, and made the workload/map cards fill that shared height cleanly. Verified with `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardWorkloadCard.jsx`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This sync is desktop-focused (`xl` and up); if visual drift still appears on the live Vercel build, the next step should be a browser-level check for font/content differences rather than another static CSS guess.

- Date: 2026-06-02
- Request: Push the dashboard queue/right-column height fix to GitHub.
- Summary: Pushed commit `ee8857ee` (`Tighten dashboard queue row layout`) to `origin/main`, publishing the measured desktop queue-height sync for the right-side stack and the removal of blank gutter space under the 10-row grievance queue.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is frontend-only and depends on Vercel picking up the `main` push; if the live UI still looks off after deploy, validate with a browser check before further layout edits.

- Date: 2026-06-02
- Request: Fix the constituency map card merging into the next dashboard row after the queue-height sync.
- Summary: Added a compact dashboard mode to `DashboardConstituencyMap`, used it in the desktop queue/workload row, and suppressed the extra hotspot chips and category tiles below the map in that constrained slot so the map card stays inside the synced row height. Verified with `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This compact behavior is intentionally scoped to the synced dashboard slot; if future designs want the chips back there, they will need a larger allocated row height rather than simply re-enabling them.

- Date: 2026-06-02
- Request: Push the compact dashboard constituency-map fix to GitHub.
- Summary: Pushed commit `b6270702` (`Compact dashboard constituency map card`) to `origin/main`, publishing the compact constituency-map mode for the synced desktop queue/workload row so the map card no longer merges into the next row.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Frontend-only; Vercel needs to finish the `main` deploy before the live dashboard reflects this compact card behavior.

- Date: 2026-06-01
- Request: Implement Phase 3 of the constituency-map architecture.
- Summary: Added DB-backed seat map manifest storage via the new `seat_map_manifests` model, upgraded `modules/seat_maps.py` to prefer admin-managed manifests over repo fallback, and introduced admin APIs to list, fetch, and upsert seat maps without requiring dashboard code changes. Added tests proving tenant map lookup still works and that an admin-upserted manifest overrides the repo default for the same seat key. Verified with `venv/bin/python -m pytest tests/test_dashboard_map_manifest_api.py -q`, `venv/bin/python -m py_compile sansadx_backend/db.py modules/seat_maps.py api_router.py admin_api.py tests/test_dashboard_map_manifest_api.py`, and `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `sansadx_backend/db.py`, `modules/seat_maps.py`, `admin_api.py`, `tests/test_dashboard_map_manifest_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The storage/control plane is ready, but there is still no admin UI for editing these manifests. Phase 4 should build a lightweight admin screen over `/api/admin/seat-maps` and eventually support asset upload/validation workflows rather than requiring raw JSON payloads.

- Date: 2026-06-01
- Request: Build Phase 2 of the constituency-map architecture.
- Summary: Added a tenant-safe backend seat-manifest contract at `/api/maps/seat-manifest`, backed by the new `modules/seat_maps.py` loader over the shared frontend map registry/manifests. Updated the dashboard overview hook to fetch the manifest from the API and pass it into the map renderer, while keeping the local manifest loader as a fallback. Added backend contract tests and refreshed the dashboard frontend test. Verified with `venv/bin/python -m pytest tests/test_dashboard_map_manifest_api.py -q`, `venv/bin/python -m py_compile api_router.py modules/seat_maps.py tests/test_dashboard_map_manifest_api.py`, and `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `modules/seat_maps.py`, `api_router.py`, `frontend/hooks/useDashboardOverview.js`, `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/tests/dashboard.test.jsx`, `tests/test_dashboard_map_manifest_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Map manifests are still repo-backed and served through the backend; Phase 3 should move registry/manifest management into admin-facing workflows or DB-backed storage so new seats do not require code changes or app redeploys.

- Date: 2026-06-01
- Request: Start building the constituency-map architecture phase by phase.
- Summary: Implemented Phase 1 by formalizing the first live map into a generic seat-registry and seat-manifest structure. Added `frontend/data/maps/registry.json`, moved Belgaum Dakshin hotspot/asset metadata into `frontend/data/maps/mla/belgaum-dakshin.manifest.json`, and refactored `frontend/lib/constituency-map-data.js` into a manifest loader instead of a one-seat config blob. Verified with `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `frontend/data/maps/registry.json`, `frontend/data/maps/mla/belgaum-dakshin.manifest.json`, `frontend/lib/constituency-map-data.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This phase still uses a static in-frontend manifest registry; the next phase should move toward a backend/API seat-manifest contract so new constituencies do not require frontend code deploys.

- Date: 2026-06-01
- Request: Push the first real constituency-map implementation to GitHub.
- Summary: Pushed commit `c0dedf04` (`Build first real constituency map`) to `origin/main`, publishing the Belgaum Dakshin real-seat SVG, seat-aware hotspot config, and the dashboard fallback strategy for unmapped constituencies.
- Files touched: `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/lib/constituency-map-data.js`, `frontend/public/maps/mla/belgaum-dakshin-outline.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The live map currently has real coverage only for Belgaum Dakshin; additional constituencies should be added through the same generic asset-plus-anchor contract rather than new component logic.

- Date: 2026-06-01
- Request: Replace the mocked dashboard constituency map with a real Belgaum Dakshin outline and real hotspot placement.
- Summary: Added a seat-aware constituency map config layer, extracted a clean Belgaum Dakshin SVG outline into `frontend/public/maps/mla/`, and rewired `DashboardConstituencyMap.jsx` to place live `red_zones` hotspots against the real seat outline for supported constituencies while preserving the previous mock map as a fallback for unmapped seats. Verified with `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`.
- Files touched: `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/lib/constituency-map-data.js`, `frontend/public/maps/mla/belgaum-dakshin-outline.svg`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The first real map only covers Belgaum Dakshin and uses curated hotspot anchors rather than true ward polygons; additional seats should reuse the same asset-plus-anchor pattern, and a future step can replace anchor heuristics with polygon/centroid data where available.

- Date: 2026-06-01
- Request: Push the UTC case-timestamp serialization fix to GitHub.
- Summary: Pushed commit `aed0b630` (`Fix case timestamp UTC serialization`) to `origin/main`, publishing the explicit-UTC `Z` timestamp contract for Briefcase case APIs so frontend `received` ages no longer drift by local timezone offsets.
- Files touched: `api_router.py`, `tests/test_briefcase_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart before live Briefcase rows pick up the corrected timestamp contract; other API surfaces may still need the same UTC pass if they serialize naive datetimes separately.

- Date: 2026-06-01
- Request: Fix Briefcase `received` ages that were drifting by about 5.5 hours because case timestamps were serialized without timezone information.
- Summary: Updated `api_router.py` so case-list/detail/export/media timestamps are normalized through `_coerce_iso()` into explicit UTC ISO strings with `Z`, including SQLite-style naive datetime strings in tests. Added Briefcase API assertions to lock the UTC contract and prevent frontend age drift from naive timestamp parsing.
- Files touched: `api_router.py`, `tests/test_briefcase_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This fixes the backend contract for affected case APIs; any remaining screens showing drift are likely consuming other endpoints that still need the same UTC serialization pass.

- Date: 2026-06-01
- Request: Push the case-language persistence and backfill batch to GitHub.
- Summary: Pushed commit `6c4e76a6` (`Persist and backfill case languages`) to `origin/main`, publishing detected-language persistence in case metadata, neutral Briefcase `UNK` fallback instead of fake `EN`, and the tenant-scoped language backfill script/tests.
- Files touched: `main.py`, `frontend/components/briefcase/briefcase-shared.jsx`, `scripts/backfill_case_languages.py`, `tests/test_case_language_backfill.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Existing rows still need the backfill script run per tenant; until then the UI will truthfully show `UNK` for missing-language historical cases instead of pretending they are English.

- Date: 2026-06-01
- Request: Fix Briefcase language badges that were showing `EN` for Marathi/Hinglish messages and add a backfill path for old cases.
- Summary: Persisted `detected_language` into case metadata during enrichment in `main.py`, changed the Briefcase language badge helper to show real mapped tags or `UNK` instead of defaulting missing values to English, and added `scripts/backfill_case_languages.py` plus focused tests to repair tenant-scoped historical rows whose language is missing or clearly mislabeled as English.
- Files touched: `main.py`, `frontend/components/briefcase/briefcase-shared.jsx`, `scripts/backfill_case_languages.py`, `tests/test_case_language_backfill.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Existing rows need the backfill script run per tenant to show corrected badges; the frontend now stops lying about missing values, so unbackfilled rows will surface as `UNK` until repaired.

- Date: 2026-06-01
- Request: Push the generalized official-corruption routing fix to GitHub.
- Summary: Pushed commit `1f81a5a0` (`Generalize corruption routing override`) to `origin/main`, publishing the structural cross-language override that rescues official bribery/payment-demand complaints into `Bureaucratic / Administrative -> Bribery/Corruption` instead of bad generic infrastructure labels.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart before live classifications pick up this generalized routing fix; future expansion should stay structural and not drift into brittle language-specific phrase hardcoding.

- Date: 2026-06-01
- Request: Fix wrong category routing for official-bribery complaints like `तलाठी पैसे मागत आहे`.
- Summary: Added a narrow high-confidence taxonomy override in `sansadx_backend/unified_taxonomy.py` so bribery or payment-demand semantics in official/revenue-office context now force `Bureaucratic / Administrative -> Bribery/Corruption` instead of falling back to bad generic infrastructure labels. Generalized the rule away from single-language phrase matching and added focused regressions covering both Marathi-script and English office-corruption complaints plus the AI normalization path.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The override is intentionally narrow; if more official-corruption patterns surface in other languages, extend the structural signal sets carefully and only when they clearly outweigh model guesses.

- Date: 2026-06-01
- Request: Push the voice-note normalization hardening batch to GitHub.
- Summary: Pushed commit `60e6dcf3` (`Harden voice note normalization pipeline`) to `origin/main`, publishing the new voice-note normalization layer, tenant-aware location candidate grounding, and raw-versus-normalized transcript preservation for future voice-note cases.
- Files touched: `modules/geography_resolver.py`, `modules/voice_note_normalizer.py`, `modules/whatsapp_media_intake.py`, `main.py`, `tests/test_voice_note_normalizer.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart before live WhatsApp voice notes start using the new normalization pass, and ambiguous transcripts should continue to fall back to clarification or review instead of forced certainty.

- Date: 2026-05-31
- Request: Push the geography validation/diagnostics/backfill hardening batch to GitHub.
- Summary: Pushed commit `1ec273d7` (`Harden geography validation and diagnostics`) to `origin/main`, publishing seat-safe onboarding validation, persisted `geography_diagnostics`, and the tenant-scoped geography backfill script/tests together as one coherent hardening batch.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The backend now stores diagnostics and has a repair tool, but there is still no dedicated admin/Briefcase UI surface for operators to inspect `geography_diagnostics` without reading raw case metadata.

- Date: 2026-05-31
- Request: Add stronger geography onboarding validation, persist geography diagnostics per case, and create a tenant-scoped backfill path for blank historical case geography.
- Summary: Extended `sanitize_and_validate_stations()` with same-seat generated-alias collision detection and weak-coverage warnings, wired all seat-geography save endpoints to reject blocking alias collisions, persisted structured `geography_diagnostics` into case metadata through `finalize_geography_decision()`/`main.py`, and added `scripts/backfill_case_geography.py` for tenant-scoped blank-geometry repair. Added focused tests for onboarding blocking behavior, diagnostics persistence, and backfill safety.
- Files touched: `modules/geography_resolver.py`, `modules/whatsapp_geography.py`, `admin_api.py`, `main.py`, `scripts/backfill_case_geography.py`, `tests/test_geography_onboarding_api.py`, `tests/test_whatsapp_geography_decision.py`, `tests/test_case_geography_backfill.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This batch does not yet add a UI for ops to view `geography_diagnostics`; the data is stored in case metadata now, but an admin/Briefcase surface would be the natural next step.

- Date: 2026-05-31
- Request: Harden geography resolution so location and assembly mapping stay tenant-safe and reliable for all current and future tenants.
- Summary: Made the geography resolver seat-aware internally by indexing assembly buckets with `seat_type + seat_name + assembly`, preferring tenant seat context during resolution, and keeping parliamentary fallback only for non-tenant-scoped lookups. Also made `save_overrides_to_db()` replace only legacy `phone_mapping` and `geo_override` rows so shared `geography_data` and generated `geo_alias` rows survive admin override saves. Added regressions for same-name cross-seat assemblies and override persistence safety.
- Files touched: `modules/geography_resolver.py`, `sansadx_backend/db.py`, `tests/test_geography_resolver.py`, `tests/test_override_persistence.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is the first hardening phase; onboarding validation, resolver diagnostics, and blank-case geography backfill are still the next improvements if we want consistently high accuracy in production.

- Date: 2026-05-31
- Request: Push the Briefcase delete-control restore to GitHub.
- Summary: Pushed commit `6e5c23f3` (`Restore Briefcase delete controls`) to `origin/main`, restoring visible bulk delete and per-row delete actions on the Briefcase dashboard while keeping the shared modal delete flow aligned with the same hook helper.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: The delete controls are now back in GitHub, but a production deploy is still required before the live Briefcase UI will show them.

- Date: 2026-05-31
- Request: Restore visible individual and bulk delete controls in the Briefcase dashboard after the table-design rollback removed them.
- Summary: Added a shared `deleteCase`/`bulkDelete` path to `useBriefcaseCases`, wired bulk delete into `BriefcaseBulkActions`, restored a per-row delete action in `BriefcaseCasesTable`, and pointed the case modal delete button at the same shared hook so Briefcase deletions now update the list, selection state, and totals consistently.
- Files touched: `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `frontend/app/dashboard/sansadx/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This was a frontend-only repair on top of the restored table design; a quick browser smoke test is still the best next check before pushing to production.

- Date: 2026-05-31
- Request: Push the one-file Briefcase table design restore to GitHub.
- Summary: Pushed commit `12eaceed` (`Restore Briefcase cases table design`) to `origin/main`, restoring the `2641837d` editorial All Cases table look in `frontend/components/briefcase/BriefcaseCasesTable.jsx`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a UI-only restore and should be browser-verified against the current Briefcase data shape before any further related design restores.

- Date: 2026-05-31
- Request: Restore only the reverted Briefcase All Cases table design from commit `2641837d`.
- Summary: Replaced `frontend/components/briefcase/BriefcaseCasesTable.jsx` with the earlier editorial table layout from `2641837d`, bringing back the denser fixed-column All Cases design without restoring the broader mobile or backend commits from that reverted batch.
- Files touched: `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This is a single-file visual restoration and has not yet been browser-verified against the current Briefcase data shape; if any newer props or interactions drifted, the next step should be a quick frontend smoke test before push.

- Date: 2026-05-31
- Request: Push the WhatsApp geography wrapper fix to GitHub.
- Summary: Pushed commit `78f7a5d8` (`Fix WhatsApp geography wrapper arg`) to `origin/main`, publishing the webhook fix that restores `location_required` pass-through into `finalize_geography_decision()`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Production still needs a backend deploy/restart on the EC2 host to pick up this commit, and OpenAI quota issues may still affect classification separately.

- Date: 2026-05-31
- Request: Fix the live WhatsApp geography regression that left new tenant 10 cases without location or assembly after ingestion.
- Summary: Patched `main.py` so `_finalize_whatsapp_geography_decision()` once again accepts and forwards the `location_required` argument to `modules.whatsapp_geography.finalize_geography_decision()`. This removes the runtime `unexpected keyword argument 'location_required'` failure that was aborting geography enrichment after case insertion.
- Files touched: `main.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This fixes the webhook argument mismatch, but live OpenAI quota issues can still degrade classification separately; production should be redeployed and retested with a fresh WhatsApp message.

- Date: 2026-05-31
- Request: Reintroduce the location-matching improvements that help MLA aspirant geography resolve real localities again after the earlier revert.
- Summary: Restored three targeted resolver fixes in `modules/geography_resolver.py`: assembly-to-parent-parliamentary scoping for MLA tenants, fuzzy keyword threshold `>93` for common Indian spelling variants, and independent indexing of newline-separated locality lines. Added resolver regressions covering multiline localities and MLA tenant scoping.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This improves matching coverage without restoring the broader reverted commit stack, but if tenant 10's saved geography itself is incomplete we may still need alias/data cleanup for missing localities.

- Date: 2026-05-31
- Request: Revert all GitHub pushes newer than `127fce16` while keeping `166db58e` and `127fce16`.
- Summary: Safely reverted the 14 commits on `main` that landed after `127fce16`, including the later seed-endpoint fixes, debug endpoints, geography persistence fixes, WhatsApp reply changes, fuzzy-matching tweak, and Briefcase table redesign. The revert was done with standard `git revert` commits so history remains intact.
- Files touched: `admin_api.py`, `api_router.py`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `main.py`, `sansadx_backend/db.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The repository is now back to the state represented by `127fce16` plus earlier history; any functionality introduced only by the reverted commits will need to be reintroduced deliberately later if still needed.

- Date: 2026-05-29
- Request: Push the constituency-specific synthetic grievance seeder to GitHub.
- Summary: Pushed commit `166db58e` (`Add constituency case seed endpoint`) to `origin/main`, including the protected `/api/admin/seed-constituency-cases` endpoint, geography-aware synthetic seed generation capped at 500 cases, selective rerun cleanup for prior synthetic cases, and focused API tests.
- Files touched: `admin_api.py`, `tests/test_constituency_case_seed_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The endpoint is now in Git history, but actually populating the live `Jadhav` tenant still requires the backend deployment to pick up this commit and an authenticated admin request against production.

- Date: 2026-05-29
- Request: Implement a safer constituency-specific synthetic grievance seeder for aspirant/demo accounts, capped at 500 cases.
- Summary: Added a protected `/api/admin/seed-constituency-cases` endpoint that targets one tenant by `tenant_id` or `username`, clears only prior synthetic seeded cases for that tenant, and generates up to 500 tagged synthetic grievances using shared seat geography localities and assemblies when available, with focused API tests covering geography-aware insertion and rerun replacement behavior.
- Files touched: `admin_api.py`, `tests/test_constituency_case_seed_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The endpoint is implemented and tested locally, but actually populating the real `Jadhav` tenant on `backend.coinmedia.co.in` still requires authenticated admin access to that live backend.

- Date: 2026-05-29
- Request: Push the tenant-aware geography reuse flow to GitHub.
- Summary: Pushed commit `9c4387a5` (`Add tenant-aware geography reuse flow`) to `origin/main`, including the launch-readiness geography redirect, the tenant-aware reuse-vs-upload chooser on the geography page, the constituency sync fix across tenant/profile/user records, and focused admin test coverage.
- Files touched: `admin/app/dashboard/mps/[tenant_id]/setup/page.js`, `admin/app/dashboard/geography/page.js`, `admin_api.py`, `admin/tests/setup-checklist.test.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Shared geography reuse still relies on exact seat-name matching; if operators later need alias-based or fuzzy seat matching, that should be added intentionally.

- Date: 2026-05-29
- Request: Make the launch-readiness geography step support either uploading new geography or reusing existing shared seat geography from rival/same-seat accounts.
- Summary: Redirected the setup checklist geography CTA to the dedicated geography page, added a tenant-aware chooser flow there that prefills the tenant seat and offers `use existing shared geography` before the upload form, and fixed the admin constituency update endpoint to keep tenant/profile/user constituency fields aligned when an account is linked to an existing saved seat.
- Files touched: `admin/app/dashboard/mps/[tenant_id]/setup/page.js`, `admin/app/dashboard/geography/page.js`, `admin_api.py`, `admin/tests/setup-checklist.test.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This reuses shared geography by seat name; if operators later need fuzzy matching or alias-based seat selection, we should add that deliberately instead of auto-linking near matches.

- Date: 2026-05-29
- Request: Push the aspirant rollout and follow-up Briefcase permission fix to GitHub.
- Summary: Rebasing local commits onto `origin/main` after the upstream Briefcase mobile merge, then pushed `a6bd8137` (`Add aspirant seat model and shared geography flow`) and `f235d7a0` (`Align Briefcase modal with primary accounts`) to `origin/main`.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Remote history now contains the full aspirant/account-stage rollout plus the final Briefcase primary-account alignment; remaining follow-up work is optional cleanup only.

- Date: 2026-05-29
- Request: Finish the account-model rollout by aligning the remaining Briefcase modal actions with primary-account permissions before pushing.
- Summary: Updated the Briefcase case modal to use shared `isPrimaryAccount` logic for citizen notifications, adjusted the related UI copy from MP-only wording to primary-account wording, and allowed `owner` accounts to retain delete-case access alongside legacy `mp` and `pr` roles.
- Files touched: `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This closes an omitted frontend permission check from the larger rollout; deeper parliamentary drafting/research wording remains intentionally elected-office-specific.

- Date: 2026-05-29
- Request: Begin the aspirant/MP identity rollout by implementing Phase 1 of the account model changes.
- Summary: Added explicit `tenant_type` handling to tenant creation and auth payloads, switched new primary customer accounts to `role='owner'` while keeping legacy `role='mp'` accounts compatible, updated key admin/frontend screens to recognize the new owner identity, and exposed account type selection in the admin create-account flow.
- Files touched: `admin_api.py`, `api_router.py`, `admin/app/dashboard/mps/new/page.js`, `admin/app/dashboard/rules/page.js`, `frontend/app/dashboard/page.js`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/settings/page.js`, `frontend/components/Sidebar.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/schemes/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Geography/setup helpers still contain same-constituency assumptions and module access is not yet gated by `tenant_type`; those belong to the next rollout phases.

- Date: 2026-05-29
- Request: Implement Phase 2 of the aspirant/MP rollout by making session/account-type handling consistent across the frontend.
- Summary: Added shared frontend account helpers, enriched login and `/auth/me` payloads with `is_primary_account` and `account_label`, switched key frontend module gates to use centralized account-type logic, and normalized remaining “MP-only” messaging to “primary account” or “elected-office accounts” where appropriate.
- Files touched: `api_router.py`, `frontend/lib/account.js`, `frontend/app/dashboard/page.js`, `frontend/app/dashboard/layout.js`, `frontend/components/Sidebar.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `frontend/app/dashboard/settings/page.js`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/schemes/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Phase 2 centralizes frontend gating logic, but actual business feature locks by `tenant_type` still need explicit backend enforcement in the next phase.

- Date: 2026-05-29
- Request: Implement Phase 3 of the aspirant/MP rollout by locking Sansad AI and Convergence for aspirants.
- Summary: Added backend feature-access enforcement for Sansad AI and Convergence APIs, refined frontend access helpers so only those two modules are gated by tenant type, hid the protected nav/buttons/routes for aspirants, added a direct Convergence route guard on company detail pages, and restored Schemes as an allowed module instead of incorrectly bundling it into the elected-office lock.
- Files touched: `api_router.py`, `frontend/lib/account.js`, `frontend/components/Sidebar.js`, `frontend/app/dashboard/layout.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardEmptyState.jsx`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/csr/company/[slug]/page.js`, `frontend/app/dashboard/schemes/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Same-constituency helper assumptions in geography/setup flows still need cleanup, and future module launches should choose feature-specific tenant-type gates instead of reusing old MP-only role checks.

- Date: 2026-05-29
- Request: Implement the post-Phase-3 account-model expansion for aspirant MP/MLA accounts and build Phase 4 geography safety.
- Summary: Split tenant identity into `account_stage` and `seat_type`, updated admin create/edit flows plus auth/session payloads to carry those fields, kept legacy `tenant_type` compatibility, and moved geography persistence to shared seat-level keys so multiple aspirants and elected accounts can safely share one seat while generated overrides remain tenant-specific.
- Files touched: `sansadx_backend/db.py`, `main.py`, `modules/geography_resolver.py`, `admin_api.py`, `api_router.py`, `frontend/lib/account.js`, `frontend/components/Sidebar.js`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/page.js`, `frontend/app/dashboard/sansadai/page.js`, `frontend/app/dashboard/csr/page.js`, `frontend/app/dashboard/csr/company/[slug]/page.js`, `frontend/app/dashboard/schemes/page.js`, `frontend/components/dashboard/DashboardEmptyState.jsx`, `admin/app/dashboard/mps/new/page.js`, `admin/app/dashboard/profiles/page.js`, `admin/app/dashboard/mps/[tenant_id]/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The generic admin geography routes are still MP-seat-shaped (`/geography/{pc}/...`), so a later cleanup should either add explicit seat-type-aware admin tooling or rename those routes/UI concepts to a more neutral seat model.

- Date: 2026-05-29
- Request: Make the admin geography UX seat-aware and validate the new shared-seat model with focused tests.
- Summary: Extended the global admin geography routes to accept `seat_type`, rebuilt the admin geography upload/browser page around explicit `MP Seat` vs `MLA Seat` selection, updated nearby admin copy from MP-only language to account/seat language, refreshed overview stats/cards for the broader account model, and added a focused geography UI test alongside updated admin dashboard coverage.
- Files touched: `admin_api.py`, `admin/app/dashboard/geography/page.js`, `admin/app/dashboard/rules/page.js`, `admin/app/dashboard/layout.js`, `admin/app/dashboard/page.js`, `admin/app/dashboard/mps/[tenant_id]/setup/page.js`, `admin/tests/dashboard.test.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The generic route names still use legacy `parliamentary`/`pc` terminology under the hood; a future cleanup can rename that API surface more neutrally once downstream callers are ready.

- Date: 2026-05-29
- Request: Finish the same-seat safety pass and permission audit after the seat-aware rollout.
- Summary: Verified shared-seat geography fan-out with a backend isolation test, hardened admin staff APIs so primary `owner`/legacy `mp` accounts cannot appear in staff management or be manipulated via staff endpoints, aligned the staff UI copy to tenant/account language, and fixed the ORM/User schema drift by adding the existing `phone` column to the `User` model.
- Files touched: `admin_api.py`, `sansadx_backend/db.py`, `admin/app/dashboard/staff/page.js`, `tests/test_same_seat_isolation.py`, `tests/test_admin_staff_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The permission audit found plenty of MP-specific copy/prompting in parliamentary research and drafting modules, but those are product-language issues rather than tenant-isolation bugs; they can be normalized later if the product expands beyond parliamentary positioning.

- Date: 2026-05-29
- Request: Apply the first aspirant-facing UI copy pass on the MP frontend.
- Summary: Updated high-visibility user-facing copy to feel more intentional for aspirants by shifting settings/profile language toward `workspace` and `team`, replacing an `MP office` triage note in Briefcase, and renaming the dashboard schedule reference from `Constituency Office` to `Constituency Workspace`.
- Files touched: `frontend/app/dashboard/settings/page.js`, `frontend/components/dashboard/DashboardEngagementsCard.jsx`, `frontend/components/briefcase/BriefcaseTriageStrip.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This was intentionally a narrow copy pass; deeper product-language normalization in drafting/research/parliamentary modules should stay separate so we do not blur features that are still meant only for elected-office contexts.

- Date: 2026-05-29
- Request: Do a broader UI-only frontend wording cleanup after the first aspirant copy pass.
- Summary: Normalized more shared-workspace labels across the MP frontend by replacing remaining generic fallbacks like `MP`, `Member`, `PA / Staff`, and `MP Office` on non-parliamentary screens, including Briefcase header/escalation copy, dashboard layout fallback initials, and settings/team action labels.
- Files touched: `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseEscalationModal.jsx`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/settings/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Parliamentary drafting/research flows still intentionally use MP-specific language; those should only be generalized later if the underlying product behavior changes too.

- Date: 2026-05-26
- Request: Establish a repo memory and confirmation-first workflow before future code changes.
- Summary: Added a mandatory pre-change protocol to `AGENTS.md` and created `PROJECT_MEMORY.md` plus `TASK_LOG.md` as persistent context files for future sessions.
- Files touched: `AGENTS.md`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The workflow depends on consistently updating memory after meaningful changes; future tasks should keep these files current.

- Date: 2026-05-26
- Request: Make memory-file maintenance mandatory after each change and each GitHub push, then push the workflow docs.
- Summary: Updated the repo protocol so `PROJECT_MEMORY.md` and `TASK_LOG.md` must be maintained after every completed change and every GitHub push.
- Files touched: `AGENTS.md`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The process is only effective if every future task closes by updating these files before or alongside the push.

- Date: 2026-05-26
- Request: Push the repo memory workflow to GitHub.
- Summary: Pushed commit `afcda31f` (`Add repo memory workflow`) to `origin/main` so the new discuss-first and memory-maintenance process is now shared in GitHub.
- Files touched: `AGENTS.md`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Future pushes should continue adding a short push record here to preserve deployment and workflow history.

- Date: 2026-05-26
- Request: Revert the MP dashboard redesign and push the rollback.
- Summary: Reverted commit `5c031838` (`Redesign MP dashboard experience`) after the user judged the redesign not ready, restoring the prior MP dashboard implementation and documenting the rollback in repo memory.
- Files touched: `frontend/app/layout.js`, `frontend/app/globals.css`, `frontend/components/Sidebar.js`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Any future redesign should be applied in smaller slices and visually verified before pushing to `main`.

- Date: 2026-05-26
- Request: Start refactoring the current Claude-built dashboard into reusable structure without changing the design.
- Summary: Completed the first refactor batch by extracting dashboard theme tokens and shared visual primitives, wiring the live dashboard page to use them, and updating the dashboard test to match the current console dashboard copy.
- Files touched: `frontend/lib/dashboard-theme.js`, `frontend/components/dashboard/DashboardMiniBars.jsx`, `frontend/components/dashboard/DashboardDonut.jsx`, `frontend/components/dashboard/DashboardSectionFrame.jsx`, `frontend/components/dashboard/DashboardStatusBadge.jsx`, `frontend/app/dashboard/page.js`, `frontend/tests/dashboard.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The dashboard page is still structurally large; the next batch should extract feature sections like KPI tiles, grievance queue, workload, letters, press, and activity feed into `frontend/components/dashboard/`.

- Date: 2026-05-26
- Request: Implement Batch 2 of the dashboard refactor by extracting feature sections into reusable components.
- Summary: Moved the major dashboard sections out of `frontend/app/dashboard/page.js` into dedicated `frontend/components/dashboard/` modules, leaving the page as an overview composer with fetching and routing logic.
- Files touched: `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `frontend/components/dashboard/DashboardWorkloadCard.jsx`, `frontend/components/dashboard/DashboardEngagementsCard.jsx`, `frontend/components/dashboard/DashboardLettersCard.jsx`, `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/components/dashboard/DashboardActivityFeed.jsx`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/components/dashboard/DashboardEmptyState.jsx`, `frontend/app/dashboard/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The next batch should separate data shaping and request orchestration into a dashboard hook and mapper layer so the page no longer owns fetch timing or response normalization.

- Date: 2026-05-26
- Request: Implement Batch 3 of the dashboard refactor by moving fetch orchestration and response shaping out of the page.
- Summary: Added `frontend/hooks/useDashboardOverview.js` for overview data loading and `frontend/lib/dashboard-mappers.js` for response normalization and derived state, then refactored `frontend/app/dashboard/page.js` to consume the hook as a composition-only screen.
- Files touched: `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `frontend/app/dashboard/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The current dashboard structure is now much healthier; the next improvements would be smaller polish items such as moving remaining inline layout styles into reusable wrappers or extending the extracted dashboard system into other MP frontend pages.

- Date: 2026-05-26
- Request: Review the dashboard refactor and push it if clean.
- Summary: Reviewed the refactor, fixed two issues before push: nondeterministic KPI chart rendering in `DashboardKpiTiles` and a false empty-state flash risk in `useDashboardOverview` when summary loaded before cases.
- Files touched: `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/hooks/useDashboardOverview.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The dashboard refactor is now structurally sound enough to push; future work can focus on broader reuse and smaller visual cleanup rather than core architecture.

- Date: 2026-05-26
- Request: Push the dashboard refactor to GitHub.
- Summary: Pushed commit `79a43a5d` (`Refactor dashboard into reusable modules`) to `origin/main`, including the extracted dashboard component system, theme tokens, mapper layer, overview hook, updated tests, and final review fixes.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `frontend/lib/dashboard-theme.js`, `frontend/components/dashboard/*`, `frontend/tests/dashboard.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Future work can now focus on reusing the dashboard system in other MP pages or doing targeted polish, rather than untangling overview-page architecture.

- Date: 2026-05-26
- Request: Start reusing the refactor pattern in Briefcase and rename the sidebar labels to Briefcase and Letterbox.
- Summary: Extracted the embedded Briefcase modal/viewer stack into `frontend/components/briefcase/`, moved shared Briefcase tabs and status helpers into a dedicated module, and renamed the sidebar labels from Grievances/Letters to Briefcase/Letterbox without changing the live Briefcase behavior.
- Files touched: `frontend/components/Sidebar.js`, `frontend/app/dashboard/sansadx/page.js`, `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/components/briefcase/BriefcaseContactPanel.jsx`, `frontend/components/briefcase/BriefcaseEscalationModal.jsx`, `frontend/components/briefcase/BriefcaseSourceMediaViewer.jsx`, `frontend/components/briefcase/BriefcaseCaseModal.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: `frontend/app/dashboard/sansadx/page.js` is still large because the toolbar, bulk-action bar, and main case table are still inline; the next Briefcase batch should extract those higher-level sections or move state orchestration into a dedicated hook.

- Date: 2026-05-26
- Request: Complete the Briefcase structural refactor before review and push.
- Summary: Finished the remaining Briefcase extraction by moving page orchestration into `frontend/hooks/useBriefcaseCases.js` and splitting the route view into dedicated components for header, filters, active filters, bulk actions, clusters, deleted cases, main case table, and pagination.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseNewCasesNotice.jsx`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `frontend/components/briefcase/BriefcaseActiveFilters.jsx`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseClustersView.jsx`, `frontend/components/briefcase/BriefcaseDeletedCasesView.jsx`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `frontend/components/briefcase/BriefcasePagination.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The Briefcase page is now structurally modular, so future work should focus on visual standardization or extracting any remaining shared patterns across Letterbox, Drafter, and Sansad AI rather than further untangling `sansadx/page.js`.

- Date: 2026-05-26
- Request: Push the completed Briefcase refactor to GitHub.
- Summary: Pushed commit `d35fd3de` (`Refactor Briefcase into reusable modules`) to `origin/main`, including the Briefcase hook/component extraction, sidebar naming updates, and repo memory updates.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/*`, `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The Briefcase page is now structurally ready for future visual-system work; the next reuse target can move to Letterbox or another MP module without carrying the old monolith shape forward.

- Date: 2026-05-26
- Request: Remove the desktop `Owner` column from the dashboard grievance queue so `Category` and `Subject` have more room.
- Summary: Removed the `Owner` column from the desktop grievance queue table in the dashboard overview and updated the empty-state column span so the queue layout can give more space to the remaining columns.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This is a dashboard-overview-only change; if the same column should disappear elsewhere, Briefcase and other queue-style tables would need separate updates.

- Date: 2026-05-26
- Request: Push the dashboard grievance queue column change to GitHub.
- Summary: Pushed commit `4293f1a3` (`Remove owner column from dashboard queue`) to `origin/main`, including the desktop grievance queue column removal and the task log update.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This only changes the dashboard overview queue; other queue/table surfaces still retain their current columns unless changed separately.

- Date: 2026-05-26
- Request: Add clearer separation between the dashboard queue `Category` and `Subject` columns on desktop.
- Summary: Added truncation plus a vertical divider to the `Category` cell and extra left padding on `Subject` so long category values no longer visually merge into the subject text.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This is still a desktop dashboard-queue adjustment only; if tighter spacing appears elsewhere, those tables will need their own spacing pass.

- Date: 2026-05-26
- Request: Push the dashboard queue spacing fix to GitHub.
- Summary: Pushed commit `84778752` (`Adjust dashboard queue column spacing`) to `origin/main`, including the category/subject spacing fix and the task log update.
- Files touched: `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This remains scoped to the dashboard overview queue; any similar spacing issues elsewhere will need separate changes.

- Date: 2026-05-26
- Request: Rebuild Briefcase to match the `Needle-2.zip` prototype as closely as possible while preserving the live workflows.
- Summary: Translated the prototype into the live Briefcase route by shifting the default state to `Needs you`, adding a triage KPI strip and promoted-clusters banner, redesigning the filters/bulk action shell, restyling the clusters and deleted views, and wiring the route composition to the new prototype-based Briefcase surface.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseActiveFilters.jsx`, `frontend/components/briefcase/BriefcaseClustersView.jsx`, `frontend/components/briefcase/BriefcaseDeletedCasesView.jsx`, `frontend/components/briefcase/BriefcaseNewCasesNotice.jsx`, `frontend/components/briefcase/BriefcaseTriageStrip.jsx`, `frontend/components/briefcase/BriefcaseClustersBanner.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The visual translation is now in place, but the remaining gap to the prototype is mostly fine-grain polish in table density and modal/detail surfaces rather than core layout or architecture.

- Date: 2026-05-26
- Request: Push the Needle-2 Briefcase redesign to GitHub.
- Summary: Pushed commit `8ae4f3c8` (`Redesign Briefcase to match prototype`) to `origin/main`, including the triage-first Briefcase layout, promoted cluster banner, redesigned filters and bulk actions, and the supporting Briefcase hook/state updates.
- Files touched: `frontend/app/dashboard/sansadx/page.js`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/*`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The core prototype translation is now live in Git history; any future iteration should focus on smaller visual polish passes rather than another large structural shift.

- Date: 2026-05-26
- Request: Revert commits `ee0be990` and `f1839330` because the mobile pass changed the Briefcase structure too much.
- Summary: Reverted commit `f1839330` (`Log Briefcase mobile push`) and commit `ee0be990` (`Make Briefcase mobile friendly`). The clarified direction is that mobile responsiveness should keep the desktop structure aligned as closely as possible instead of switching to alternate mobile-specific layouts.
- Files touched: `frontend/app/dashboard/layout.js`, `frontend/components/briefcase/BriefcaseHeader.jsx`, `frontend/components/briefcase/BriefcaseTriageStrip.jsx`, `frontend/components/briefcase/BriefcaseClustersBanner.jsx`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `frontend/components/briefcase/BriefcaseBulkActions.jsx`, `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `frontend/components/briefcase/BriefcaseDeletedCasesView.jsx`, `frontend/components/briefcase/BriefcaseClustersView.jsx`, `frontend/components/briefcase/BriefcasePagination.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The next mobile pass should focus on alignment-preserving responsive refinement rather than separate phone-only structures.

- Date: 2026-05-26
- Request: Push the Briefcase mobile rollback to GitHub.
- Summary: Pushed the rollback sequence to `origin/main`: `72b1491f` (`Revert "Log Briefcase mobile push"`), `514076c7` (`Revert "Make Briefcase mobile friendly"`), and `7b861b15` (`Document Briefcase mobile rollback`).
- Files touched: `frontend/app/dashboard/layout.js`, `frontend/components/briefcase/*`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Future MP mobile responsiveness work should preserve desktop structure and alignment first, then apply only minimal responsive adaptations.

- Date: 2026-05-27
- Request: Make `All cases` the first and default Briefcase tab, and restore `Others` for greetings, offensive/spam, and personal request messages.
- Summary: Reordered the Briefcase tabs so `All cases` is first and becomes the default when no status query param is present, restored `Others` as a real tab, and wired it to the backend-supported `bucket=other` filter path instead of a custom frontend-only parameter.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/app/dashboard/sansadx/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: `Others` currently follows the backend's `other` bucket definitions plus the shared frontend labels; if you want to refine exactly which categories count as “personal request,” we should align the backend bucket list too.

- Date: 2026-05-27
- Request: Push the Briefcase default-tab and `Others` restoration to GitHub.
- Summary: Pushed commit `9915251c` (`Restore Briefcase all-cases default`) to `origin/main`, including the `All cases` default/tab order change and the restored `Others` bucket using the backend-supported `bucket=other` filter.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/app/dashboard/sansadx/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: If `Others` needs a more exact “personal request” definition, the backend bucket list should be tuned alongside the frontend labels.

- Date: 2026-05-27
- Request: Remove the `Needs you` Briefcase tab but keep the same idea in the triage stats.
- Summary: Removed `Needs you` from the Briefcase tab strip and quick filters, kept `All cases` as the default operational view, and retained the “needs attention” number only in the triage metrics derived from new, pending-review, awaiting-location, and escalated cases.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The triage stat still reflects the same attention bucket, but there is no dedicated one-click tab for it anymore.

- Date: 2026-05-27
- Request: Push the Briefcase `Needs you` tab removal to GitHub.
- Summary: Pushed commit `261e3315` (`Remove Briefcase needs-you tab`) to `origin/main`, keeping the triage “needs attention” metric while removing the tab itself from Briefcase.
- Files touched: `frontend/components/briefcase/briefcase-shared.jsx`, `frontend/hooks/useBriefcaseCases.js`, `frontend/components/briefcase/BriefcaseFiltersBar.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The triage number remains available, but users can no longer jump directly into that subset through a dedicated Briefcase tab.

- Date: 2026-05-27
- Request: Remove the duplicate global dashboard header on Briefcase so only the Briefcase header shows there.
- Summary: Updated the shared dashboard layout to suppress its generic route header on `/dashboard/sansadx`, leaving the page-level Briefcase header as the only visible header on that route.
- Files touched: `frontend/app/dashboard/layout.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is intentionally scoped to Briefcase; other pages still use the shared “Operations Dashboard” header until we decide otherwise.

- Date: 2026-05-27
- Request: Push the Briefcase duplicate-header fix to GitHub.
- Summary: Pushed commit `0a90e89d` (`Hide shared header on Briefcase`) to `origin/main`, so the Briefcase route now shows only its own page header instead of stacking the shared dashboard header above it.
- Files touched: `frontend/app/dashboard/layout.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The suppression is route-specific to Briefcase; if we want the same behavior on other pages later, we should make that a deliberate shared-layout rule.

- Date: 2026-05-27
- Request: Restore the older Media Centre behavior on the dashboard so press monitoring shows separate national and local feeds again, while keeping the logic tenant-aware.
- Summary: Replaced the simplified single-feed press card with a dual-tab `Media Centre`, updated the overview hook and mappers to fetch and normalize both `national` and `local` news feeds in parallel, and expanded the tenant-aware local news query strategy in `modules/news_intel.py` to use profile languages, constituency aliases, and broader digital-media search terms without hardcoding any single constituency.
- Files touched: `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `modules/news_intel.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The local feed is now broader and more multilingual, but it still depends on Google News-indexed sources; true direct social-handle/page monitoring would need a separate ingestion layer later.

- Date: 2026-05-27
- Request: Push the restored tenant-aware Media Centre to GitHub.
- Summary: Pushed commit `1d0e4dc7` (`Restore tenant-aware dashboard media centre`) to `origin/main`, restoring separate dashboard media tabs for national and local coverage while keeping the feed logic tenant-driven through the existing profile-based backend model.
- Files touched: `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/hooks/useDashboardOverview.js`, `frontend/lib/dashboard-mappers.js`, `modules/news_intel.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The dashboard now again exposes both feed types, but local social/page coverage is still limited to sources discoverable through the current Google News-based ingestion path.

- Date: 2026-05-27
- Request: Improve mobile responsiveness on the dashboard overview without changing the desktop structure.
- Summary: Updated the dashboard overview grids and section wrappers to collapse cleanly on smaller screens, made KPI tiles responsive, allowed the grievance queue controls to wrap while keeping the table structure via horizontal overflow, stacked Media Centre controls on narrow widths, and made map/category sections adapt better to phones without introducing alternate mobile-only layouts.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardSectionFrame.jsx`, `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/components/dashboard/DashboardActivityFeed.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This pass is intentionally overview-only; if you want the same alignment-preserving responsive treatment on other MP pages, we should do them individually rather than assume one pattern fits all.

- Date: 2026-05-27
- Request: Push the dashboard mobile responsiveness update to GitHub.
- Summary: Pushed commit `a2bfd2bf` (`Improve dashboard mobile responsiveness`) to `origin/main`, keeping the dashboard’s desktop structure intact while making its grids, controls, and dense sections behave better on smaller screens.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardSectionFrame.jsx`, `frontend/components/dashboard/DashboardKpiTiles.jsx`, `frontend/components/dashboard/DashboardGrievanceQueue.jsx`, `frontend/components/dashboard/DashboardPressCard.jsx`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `frontend/components/dashboard/DashboardActivityFeed.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This push only covers the dashboard overview; Briefcase, Letterbox, Sansad AI, and other MP pages will need their own responsive passes.

- Date: 2026-05-29
- Request: Redesign the Briefcase cases table to match the "All cases" variant from the Needle-3 design ZIP.
- Summary: Rewrote `BriefcaseCasesTable.jsx` as a fixed-layout native `<table>` with `<colgroup>` pixel widths matching the design. Added: left 3px accent bar (saffron=critical, green=selected), stacked citizen name + phone, stacked sub-category + domain, stacked location + assembly, `StatusPill` with icon+label from `briefcasePalette`, language badge + 2-line clamped message, hover-reveal action buttons, and skeleton loader rows. Pushed as commit `2641837d`.
- Files touched: `frontend/components/briefcase/BriefcaseCasesTable.jsx`, `TASK_LOG.md`
- Risks or follow-ups: Frontend deploys via Vercel on push to main. Backend (EC2) has no changes in this commit. Visual verification against the design should be done once Vercel deploy completes.

- Date: 2026-05-29
- Request: Fix Jadhav's seeded cases showing only "Nanawadi" — data looked fake for demo.
- Summary: Root cause was twofold: (1) seed was called with count=1 in a loop, so idx=0 always picked localities[0]="Nanawadi"; (2) count>500 bulk seed failed because SQLAlchemy 2.x batches session.add() objects into a typed executemany that casts String columns as ::VARCHAR, rejected when assigned_to column is still INTEGER. Fixed by adding db.flush() after each Case add (forces individual single-row INSERTs, NULL sent untyped). Seeded 500 cases across all 69 Belgaum dakshin localities for tenant_id=10. Commits: 41c9193e, f48bd38c, 5e3349dd.
- Files touched: `admin_api.py`, `TASK_LOG.md`
- Risks or follow-ups: The assigned_to INTEGER column is still on the DB — the startup migration keeps getting skipped. The flush workaround is solid but the ALTER COLUMN migration should be investigated and cleaned up later.

- Date: 2026-05-31
- Request: Change citizen WhatsApp intake so the first response stays a normal acknowledgment, clarification for missing location/details is delayed by 2–3 minutes, and later citizen clarifications update the original case automatically.
- Summary: Added a shared citizen-case enrichment path in `main.py`, delayed clarification scheduling via case metadata plus background timers/startup sweep, and a follow-up intercept that enriches the original recent clarification-pending case instead of inserting a new one. The first citizen reply now stays generic even for `awaiting_location` / `incomplete`, while the delayed second message asks for location or more detail only when needed.
- Files touched: `main.py`, `tests/test_citizen_clarification_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The timing is handled in-process plus startup recovery, so truly guaranteed delayed delivery across crashes would eventually benefit from a dedicated job queue; for now the metadata + startup sweep path covers deploy/restart recovery.

- Date: 2026-05-31
- Request: Push the delayed citizen clarification follow-up flow to GitHub.
- Summary: Pushed commit `abb16bfe` (`Delay citizen clarification follow-ups`) to `origin/main`, including the delayed clarification scheduler, same-case clarification enrichment, and focused citizen intake tests.
- Files touched: `main.py`, `tests/test_citizen_clarification_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is pushed but not yet deployed to EC2, so live WhatsApp behavior will not change until the backend is redeployed.

- Date: 2026-05-31
- Request: Switch WhatsApp voice-note reading from the old multimodal path to Sarvam AI because the current transcription quality is poor.
- Summary: Added `core/sarvam_client.py` and routed `modules/whatsapp_media_intake.py` to use Sarvam STT first for `media_type="audio"`, while keeping Gemini as the fallback and leaving image/document handling unchanged. Added focused media-intake test coverage for the Sarvam-first audio path.
- Files touched: `core/sarvam_client.py`, `modules/whatsapp_media_intake.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is an audio-only provider swap. If Sarvam’s API shape or auth header changes, voice notes will fall back to Gemini, so production should be tested with real WhatsApp OGG voice notes after deploy.

- Date: 2026-05-31
- Request: Push the Sarvam voice-note transcription swap to GitHub.
- Summary: Pushed commit `036bcfbf` (`Use Sarvam for voice note transcription`) to `origin/main`, publishing the new Sarvam-first audio transcription path with Gemini fallback and the focused media-intake tests.
- Files touched: `core/sarvam_client.py`, `modules/whatsapp_media_intake.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The live backend still needs a deploy/restart before WhatsApp voice notes start using Sarvam in production.

- Date: 2026-05-31
- Request: Improve future voice-note reading and mapping accuracy across languages and issue types, not just for a single corrected case.
- Summary: Added a new `modules/voice_note_normalizer.py` layer that sits between Sarvam transcription and grievance classification, builds a tenant-scoped shortlist of likely localities using resolver candidates, and uses Gemini to conservatively clean ASR drift without translating the citizen’s language. Media intake now preserves both the raw transcript and normalized complaint text in source-media metadata, and the geography resolver exposes `suggest_location_candidates()` for voice-note grounding.
- Files touched: `modules/geography_resolver.py`, `modules/voice_note_normalizer.py`, `modules/whatsapp_media_intake.py`, `main.py`, `tests/test_voice_note_normalizer.py`, `tests/test_whatsapp_media_intake.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This materially improves the pipeline, but true production confidence still depends on live OpenAI/Gemini quota health and real-world evaluation across diverse voice notes; ambiguous cases should still fall back to clarification or review instead of forced certainty.

- Date: 2026-06-01
- Request: Build Phase 4 of the constituency map architecture so seat maps can be managed operationally instead of through raw JSON or code-only edits.
- Summary: Added a new admin seat-map management page at `/dashboard/seat-maps`, linked it into the admin sidebar/layout, and wired it to `/api/admin/seat-maps` for listing and saving DB-backed seat manifests. The UI supports seat metadata, aliases, asset configuration, features, and fallback anchors with client-side validation for missing required fields, duplicate aliases, and invalid anchor coordinates.
- Files touched: `admin/app/dashboard/layout.js`, `admin/components/Sidebar.js`, `admin/app/dashboard/seat-maps/page.js`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Asset management is still path-based rather than upload-based, so Phase 4 is operational but not yet a full asset pipeline. Future work can add asset upload/storage and stronger server-side manifest validation if needed.

- Date: 2026-06-01
- Request: Push and deploy the constituency map architecture through Phase 4.
- Summary: Pushed commit `c23f4315` (`Build seat map admin architecture`) to `origin/main`, covering the Phase 2 backend manifest API, Phase 3 DB-backed/admin-managed manifest storage, and Phase 4 admin seat-map management UI. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, and verifying `https://backend.coinmedia.co.in/health` returned `ok`. Temporary SSH ingress on the EC2 security group was revoked after deploy.
- Files touched: `PROJECT_MEMORY.md`, `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Vercel still needs to pick up the pushed frontend/admin changes through its normal deployment flow. Backend APIs are live; if the admin UI does not appear immediately, wait for the Vercel build to finish or redeploy the frontend projects.

- Date: 2026-06-01
- Request: Add a one-click constituency map generator so a seat map can be created without uploading any asset manually.
- Summary: Added `modules/seat_map_generator.py`, which builds a generated SVG background plus locality feature anchors directly from shared seat geography (`geography_data`). Added `POST /api/admin/seat-maps/generate` to create/update a DB-backed seat manifest in one click, relaxed seat-map save validation to accept `asset.inline_svg` instead of only `asset.path`, updated the Seat Maps admin page with a new `Generate map` action, and taught the dashboard map renderer to display generated inline SVG assets through a data URI. Verified with `venv/bin/python -m pytest tests/test_seat_map_generator.py -q`, `npm run test --prefix admin -- --run tests/seat-maps.test.jsx tests/dashboard.test.jsx tests/geography.test.jsx`, `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`, and `venv/bin/python -m py_compile admin_api.py modules/seat_map_generator.py modules/seat_maps.py`.
- Files touched: `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `admin/tests/seat-maps.test.jsx`, `tests/test_seat_map_generator.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The one-click output is an operationally useful generated SVG, not a legally precise boundary geometry. It depends on shared seat geography already being present; if geography has not been uploaded for a seat, generation should fail and ask ops to upload geography first.

- Date: 2026-06-01
- Request: Remove the low-level Seat Maps admin editor and replace it with a shared-geography reuse workflow.
- Summary: Rebuilt `/dashboard/seat-maps` as a workflow-first operations screen backed by a new `GET /api/admin/seat-maps/workflow` summary endpoint. The page now lists seats by readiness, shows shared geography presence, map status, assembly/locality counts, and tenant usage, and offers a single generate/regenerate action instead of raw manifest fields. Added backend tests for the workflow endpoint and kept generation tied to shared seat geography so one generated map can safely serve every tenant on the same constituency.
- Files touched: `admin/app/dashboard/seat-maps/page.js`, `admin_api.py`, `modules/seat_maps.py`, `tests/test_dashboard_map_manifest_api.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This intentionally hides raw manifest editing from ops. If advanced overrides are ever needed later, they should be exposed in a separate expert-only surface rather than by reintroducing the full low-level editor into the main Seat Maps workflow.

- Date: 2026-06-01
- Request: Build the proper boundary-first map system: architecture first, real boundary ingestion path, and blob fallback only as backup.
- Summary: Added a new `seat_boundary_assets` registry model plus `modules/seat_boundaries.py` for real constituency geometry storage and lookup. Added admin boundary ingestion APIs (`GET /api/admin/seat-boundaries/by-key`, `POST /api/admin/seat-boundaries`), extended seat-map workflow summaries with `boundary_ready`/`boundary_type`/`boundary_source`, and updated one-click seat-map generation so it prefers a registered real boundary asset and only falls back to the generated blob when no real boundary exists. Reworked the Seat Maps admin workflow to expose real boundary registration directly in the seat operations screen. Verified with `venv/bin/python -m pytest tests/test_dashboard_map_manifest_api.py tests/test_seat_map_generator.py -q`, `npm run test --prefix admin -- --run tests/seat-maps.test.jsx tests/dashboard.test.jsx tests/geography.test.jsx`, `npm run test --prefix frontend -- --run tests/dashboard.test.jsx`, and `venv/bin/python -m py_compile admin_api.py modules/seat_maps.py modules/seat_map_generator.py modules/seat_boundaries.py tests/test_dashboard_map_manifest_api.py tests/test_seat_map_generator.py`.
- Files touched: `sansadx_backend/db.py`, `modules/seat_boundaries.py`, `modules/seat_maps.py`, `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `admin/tests/seat-maps.test.jsx`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_seat_map_generator.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The system is now architecturally correct, but it still depends on real boundary assets actually being registered seat by seat. Without those, the generator will still use the blob backup tier; that fallback should be hidden or avoided in demos whenever a real boundary asset can be provided.

- Date: 2026-06-01
- Request: Push and deploy the boundary-first seat map system.
- Summary: Pushed commit `c7ba5224` (`Build boundary-first seat map system`) to `origin/main`, publishing the `seat_boundary_assets` registry, boundary ingestion APIs, boundary-aware workflow status, and real-boundary-first generation behavior. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, confirming `https://backend.coinmedia.co.in/health` returned `ok`, and revoking the temporary SSH ingress rule afterward.
- Files touched: `PROJECT_MEMORY.md`, `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Backend support is live now, but the admin/frontend UI still depends on Vercel finishing the latest deploy from `main`. Real maps will only stop using the blob fallback once real boundary assets are actually registered seat by seat.

- Date: 2026-06-01
- Request: Push and deploy the workflow-first Seat Maps generator system.
- Summary: Pushed commit `0b51b5e5` (`Build seat map workflow generator`) to `origin/main`, publishing the shared-geography-driven one-click seat map generator, the new `/api/admin/seat-maps/workflow` endpoint, and the rebuilt Seat Maps admin surface. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, confirming `https://backend.coinmedia.co.in/health` returned `ok`, and revoking the temporary SSH ingress rule afterward.
- Files touched: `PROJECT_MEMORY.md`, `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Backend APIs are live now. The updated admin/frontend UI depends on Vercel picking up the new `main` push; if the new Seat Maps workflow page does not appear immediately, wait for the frontend/admin deploy to finish or trigger a Vercel redeploy.

- Date: 2026-06-01
- Request: Make the real seat-boundary system practical by importing real parliamentary boundaries from the downloaded open map dataset and rendering GeoJSON directly instead of requiring manual SVG conversion.
- Summary: Added `modules/parliamentary_boundary_importer.py` plus `scripts/import_parliamentary_boundaries.py` to ingest MP constituency boundaries from the Datameet `maps-master.zip` / `india_pc_2019_simplified.geojson` dataset into `seat_boundary_assets` as `asset.type="geojson"`. Added `POST /api/admin/seat-boundaries/import-parliamentary` for seat-specific admin import, updated one-click seat-map generation to treat GeoJSON boundaries as real assets, and taught `DashboardConstituencyMap.jsx` to render GeoJSON boundary geometry directly in the dashboard. The Seat Maps admin workflow now includes a file-based parliamentary dataset import action for MP seats, and regression coverage was added for GeoJSON boundary import/generation.
- Files touched: `modules/parliamentary_boundary_importer.py`, `scripts/import_parliamentary_boundaries.py`, `admin_api.py`, `modules/seat_maps.py`, `modules/seat_map_generator.py`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `admin/app/dashboard/seat-maps/page.js`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_seat_map_generator.py`, `tests/test_parliamentary_boundary_importer.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This importer currently targets the parliamentary GeoJSON path only, so it solves MP boundaries first. MLA boundary ingestion still needs a dedicated shapefile/GeoJSON conversion and validation path before it should be exposed as a similar one-click workflow.

- Date: 2026-06-01
- Request: Push and deploy the parliamentary boundary importer and GeoJSON-first map rendering changes.
- Summary: Pushed commit `7eac8ee5` (`Add parliamentary boundary importer`) to `origin/main`, publishing the MP boundary importer, admin upload path, and GeoJSON dashboard rendering updates. Deployed the backend manually on EC2 by pulling `main`, rebuilding `ec2-backend-1`, confirming `https://backend.coinmedia.co.in/health` returned `ok`, and revoking the temporary SSH ingress rule afterward.
- Files touched: `TASK_LOG.md`, deployment host `/opt/compass-needle/app`
- Risks or follow-ups: Backend support is live now, but the admin/frontend UI still depends on Vercel finishing the latest `main` deploy. The new importer currently covers the parliamentary GeoJSON path only; MLA boundary ingestion remains a follow-up.

- Date: 2026-06-01
- Request: Remove the MP dataset upload requirement and make seat selection use the built-in parliamentary boundary library automatically.
- Summary: Added the Datameet parliamentary GeoJSON into the repo at `data/maps/parliamentary/india_pc_2019_simplified.geojson`, taught `modules/parliamentary_boundary_importer.py` to load that built-in library, added `POST /api/admin/seat-boundaries/import-parliamentary-auto`, and updated `modules/seat_map_generator.py` so MP map generation attempts a built-in boundary import before any blob fallback. The Seat Maps admin UI now offers `Import MP boundary automatically` instead of requiring a file upload.
- Files touched: `data/maps/parliamentary/india_pc_2019_simplified.geojson`, `modules/parliamentary_boundary_importer.py`, `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_parliamentary_boundary_importer.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This closes the upload requirement for MP seats only. MLA boundaries still need a safe built-in ingestion path before the same experience can be exposed there.

- Date: 2026-06-01
- Request: Push the built-in parliamentary boundary library change to GitHub.
- Summary: Pushed commit `84996e26` (`Bundle parliamentary boundary library`) to `origin/main`, publishing the in-repo MP boundary dataset, automatic parliamentary boundary import endpoint, and the no-upload Seat Maps admin flow for MP constituencies.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is pushed but not deployed yet. The new no-upload MP boundary flow will appear live only after the backend and admin frontend are redeployed.

- Date: 2026-06-01
- Request: Extend the no-upload built-in boundary ingestion system to MLA seats as well, so admins never need to upload constituency datasets manually.
- Summary: Normalized the Datameet assembly shapefile into a built-in GeoJSON library at `data/maps/assembly/india_ac_normalized.geojson`, added `modules/assembly_boundary_importer.py`, generalized the admin endpoint to `POST /api/admin/seat-boundaries/import-auto`, and updated seat-map generation so both MP and MLA seats attempt built-in boundary import before any blob fallback. The Seat Maps UI now uses a single `Import real boundary automatically` action for both seat types.
- Files touched: `data/maps/assembly/india_ac_normalized.geojson`, `modules/assembly_boundary_importer.py`, `modules/seat_map_generator.py`, `admin_api.py`, `admin/app/dashboard/seat-maps/page.js`, `tests/test_dashboard_map_manifest_api.py`, `tests/test_seat_map_generator.py`, `tests/test_assembly_boundary_importer.py`, `admin/tests/seat-maps.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The built-in MLA library comes from the normalized Datameet assembly source, which still has known delimitation/naming caveats in some states. The admin experience is now upload-free, but boundary accuracy should still be spot-checked for high-stakes constituencies.

- Date: 2026-06-01
- Request: Push the built-in assembly boundary library and unified auto-import flow to GitHub.
- Summary: Pushed commit `0ddc1b8e` (`Bundle assembly boundary library`) to `origin/main`, publishing the in-repo MLA boundary dataset, `modules/assembly_boundary_importer.py`, and the shared no-upload `import-auto` seat-boundary flow for both MP and MLA seats.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is pushed but not deployed yet. The live admin workflow will keep the older behavior until the backend and admin frontend are redeployed.

- Date: 2026-06-01
- Request: Make parliamentary constituency maps use assembly constituency boundaries internally so grievance hotspots pin within the correct assembly segment instead of floating arbitrarily inside the MP outline.
- Summary: Extended `modules/assembly_boundary_importer.py` with built-in assembly lookup by parliamentary seat, updated `modules/seat_map_generator.py` so MP manifests carry `asset.assembly_geojson` and derive locality anchors from real assembly sub-boundaries when available, and taught `DashboardConstituencyMap.jsx` to render those internal assembly lines on top of the parliamentary GeoJSON outline. Added regression coverage proving MP manifests now separate hotspot anchors by assembly geography instead of the old synthetic ring layout.
- Files touched: `modules/assembly_boundary_importer.py`, `modules/seat_map_generator.py`, `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `tests/test_seat_map_generator.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This improves MP map credibility materially, but it still depends on the quality of the normalized assembly GeoJSON for each state. If a constituency's assembly shapes are wrong or stale in the source dataset, hotspot placement will still inherit that source-quality issue until the boundary library is corrected.

- Date: 2026-06-01
- Request: Push the parliamentary assembly-segment map refinement to GitHub.
- Summary: Pushed commit `db1f82ce` (`Use assembly segments inside parliamentary maps`) to `origin/main`, publishing the parliamentary-map change that uses built-in assembly sub-boundaries for MP hotspot placement and renders assembly lines inside the real parliamentary GeoJSON outline.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is pushed but not deployed yet. The live dashboard will continue using the older flat parliamentary hotspot behavior until the backend is redeployed and the frontend build picks up the new renderer.

- Date: 2026-06-01
- Request: Fix the live parliamentary assembly-segment map lookup so `Belagavi` MP seats can find the built-in assembly segments stored under older parliamentary labels like `BELGAUM`.
- Summary: Updated `modules/assembly_boundary_importer.py` so parliamentary assembly lookups prefer `PC_NO` and alias matches before canonical seat-name text, and updated `modules/seat_map_generator.py` to pass parliamentary boundary `pc_no`/aliases into that lookup. Added regression coverage proving MP map generation can resolve assembly segments even when parliamentary seat naming differs between the parliamentary and assembly datasets.
- Files touched: `modules/assembly_boundary_importer.py`, `modules/seat_map_generator.py`, `tests/test_assembly_boundary_importer.py`, `tests/test_seat_map_generator.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This should fix the `Belagavi` vs `BELGAUM` mismatch cleanly, but any other source-data naming drift should still be handled through `PC_NO` first and alias curation second rather than piling on more one-off text normalizations.

- Date: 2026-06-01
- Request: Swap the dashboard positions of the constituency map and the `Today · Schedule` card so the map takes the schedule slot and the schedule card moves into the old map slot.
- Summary: Reordered the dashboard overview composition in `frontend/app/dashboard/page.js` so `DashboardConstituencyMap` now renders in the exact row/slot previously used by `DashboardEngagementsCard`, while the schedule card now renders in the old map position next to the activity feed. This keeps the swap layout-only and preserves existing card internals.
- Files touched: `frontend/app/dashboard/page.js`, `TASK_LOG.md`
- Risks or follow-ups: This is intentionally a pure placement swap. If the schedule card feels visually too wide in the old map slot, that should be handled by tuning the schedule card itself rather than reworking the overall dashboard grid again.

- Date: 2026-06-01
- Request: Push the dashboard map/schedule card swap to GitHub for deployment.
- Summary: Pushed commit `85147f4a` (`Swap dashboard map and schedule cards`) to `origin/main`, publishing the dashboard overview layout change that moves the constituency map into the former `Today · Schedule` slot and moves the schedule card into the former map slot.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a frontend-only change. Deployment depends on Vercel picking up the new `main` push; no backend redeploy is required for this specific layout swap.

- Date: 2026-06-01
- Request: Fix parliamentary hotspot placement after the map renderer started showing assembly-aware anchors outside the actual assembly shapes.
- Summary: Corrected `DashboardConstituencyMap.jsx` so saved hotspot anchors are converted from the generator’s `100 x 72` map coordinate space into CSS percentages before rendering. The generator was already saving assembly-aware anchors, but the frontend was treating `y` as a raw percent instead of a 72-unit canvas value, which pushed MP hotspots visibly above their intended assembly regions.
- Files touched: `frontend/components/dashboard/DashboardConstituencyMap.jsx`, `TASK_LOG.md`
- Risks or follow-ups: This assumes the current seat-map anchor convention remains `x in [0,100]`, `y in [0,72]`. If future map manifests use a different canvas coordinate system, the manifest contract should expose that explicitly rather than relying on this frontend default.

- Date: 2026-06-01
- Request: Push the hotspot coordinate scaling fix to GitHub for frontend deployment.
- Summary: Pushed commit `f972321d` (`Fix map hotspot coordinate scaling`) to `origin/main`, publishing the frontend renderer fix that maps saved `100 x 72` hotspot coordinates into correct CSS percentages before drawing them on the parliamentary/assembly constituency map.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a frontend-only change. Deployment depends on Vercel picking up the latest `main` push; no backend redeploy is needed for this particular fix.

- Date: 2026-06-02
- Request: Fix dashboard blank space by showing 5 items with a `View more` toggle in the bottom-row cards.
- Summary: Updated the dashboard overview so `Activity`, `Letters & drafts`, and `Media Centre` each show 5 items by default with inline expand/collapse controls, reducing empty space without overloading the initial view. Also added a small `h-full` layout tweak in `frontend/app/dashboard/page.js` so the right-side stack stretches cleanly with the relocated constituency map.
- Files touched: `frontend/app/dashboard/page.js`, `frontend/components/dashboard/DashboardActivityFeed.jsx`, `frontend/components/dashboard/DashboardLettersCard.jsx`, `frontend/components/dashboard/DashboardPressCard.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is frontend-only and should deploy through Vercel after push. If the same blank-space pattern shows up in other dashboard cards later, reuse the same 5-item plus toggle convention instead of increasing fixed card heights.

- Date: 2026-06-02
- Request: Push the dashboard blank-space fix to GitHub for frontend deployment.
- Summary: Pushed commit `af3c094c` (`Fix dashboard blank space with view more toggles`) to `origin/main`, publishing the 5-item default plus `View more` / `View less` behavior for the lower dashboard cards and the small supporting layout adjustment in the overview page.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a frontend-only push. No EC2 backend deploy is needed; rollout depends on Vercel picking up the new `main` commit.

- Date: 2026-06-03
- Request: Finish the admin IA cleanup by removing the `Legacy Tools` sidebar section, tightening page-level copy to match the new domains, and verify the migrated admin experience end to end.
- Summary: Removed the `Legacy Tools` group from `admin/components/Sidebar.js`, leaving the new domain-first navigation as the only primary admin IA. Tightened `admin/app/dashboard/layout.js` descriptions and rewrote the new domain landing pages for `Accounts`, `Seats`, `Shared Geography`, `Cases & Intelligence`, `Staff & Access`, and `System` so they describe durable workflows rather than transitional migration state.
- Files touched: `admin/components/Sidebar.js`, `admin/app/dashboard/layout.js`, `admin/app/dashboard/accounts/page.js`, `admin/app/dashboard/seats/page.js`, `admin/app/dashboard/shared-geography/page.js`, `admin/app/dashboard/cases-intelligence/page.js`, `admin/app/dashboard/staff-access/page.js`, `admin/app/dashboard/system/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Navigation is now cleaner, but the next review should happen in the live admin UI to decide whether the `Seats` domain needs real seat-specific detail pages soon or can remain a landing hub a bit longer.

- Date: 2026-06-03
- Request: Push the full admin frontend IA migration and cleanup batch to GitHub for deployment.
- Summary: Pushed commit `f4ba967a` (`Restructure admin frontend around domain IA`) to `origin/main`, publishing the domain-first admin route tree, shared admin-domain ownership modules, legacy route redirects, updated domain landing pages, and the cleaned primary sidebar without the old `Legacy Tools` section.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is an admin frontend rollout, so deployment depends on Vercel picking up the latest `main` push. The next live review should focus on whether `Seats` needs deeper seat-detail screens and whether any remaining page copy still feels transitional.

- Date: 2026-06-03
- Request: Stop patching geography one miss at a time and harden the resolver for multi-state launch readiness.
- Summary: Upgraded `modules/geography_resolver.py` from mostly transliteration-plus-alias matching into a stronger native-first normalization path. Added native-script suffix stripping for common Indian locality inflections, broader transliterated stem variants, punctuation-preserving match forms for compound uploaded localities, and a separate `specific_keywords` scoring lane so real sub-localities like `Vaccine Depot` remain matchable even if their words look generic. Added regression coverage for Kannada inflected locality forms such as `ಪಿರನ್ವಾಡಿನ` -> `Peeranwadi` and `ಡೆಪೋನಲ್ಲಿ` -> the correct seat/assembly geography outcome.
- Files touched: `modules/geography_resolver.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is seat-generic and tenant-safe, but it is still only as good as the uploaded shared geography. The next hardening step should be broader cross-state fixtures across more scripts/languages so launch confidence is based on representative data rather than only Belagavi-shaped examples.

- Date: 2026-06-03
- Request: Push the geography hardening pass for backend deployment.
- Summary: Pushed commit `8b22fab2` (`Harden geography resolver normalization pipeline`) to `origin/main`, publishing the native-first locality normalization, stronger transliterated stem handling, and the new Kannada geography regression coverage.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is a backend resolver change, so production depends on the EC2 backend deploy workflow picking up `8b22fab2`. `tenant_overrides.json` remained intentionally unpushed.

- Date: 2026-06-03
- Request: Implement the new `Compass Needle Design System-2` visual language in the real admin frontend.
- Summary: Ported the design system into the admin app by replacing the old generic green/white styling with shared order-paper tokens and IBM Plex typography in `admin/app/globals.css`, then restyled the canonical admin shell (`Sidebar`, dashboard layout header, notification tray), the admin login page, the command-centre overview, and the new domain landing pages (`Accounts`, `Seats`, `Shared Geography`, `Cases & Intelligence`, `Staff & Access`, `System`) to match the new command-console look while preserving the current admin IA and behavior.
- Files touched: `admin/app/globals.css`, `admin/components/Sidebar.js`, `admin/components/NotificationTray.js`, `admin/app/dashboard/layout.js`, `admin/app/page.js`, `admin/app/dashboard/page.js`, `admin/app/dashboard/accounts/page.js`, `admin/app/dashboard/seats/page.js`, `admin/app/dashboard/shared-geography/page.js`, `admin/app/dashboard/cases-intelligence/page.js`, `admin/app/dashboard/staff-access/page.js`, `admin/app/dashboard/system/page.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This slice updates the shared shell and domain/home surfaces first, which is the right base for deeper admin workflows. The next pass should restyle the heavier workflow screens (`Accounts` registry/new, shared geography workspace, seat maps, case intelligence detail views) onto the same design primitives so the whole admin feels uniformly redesigned rather than shell-first.

- Date: 2026-06-03
- Request: Push the admin design-system implementation to GitHub for deployment.
- Summary: Pushed commit `ba2a42d0` (`Implement admin design system shell`) to `origin/main`, publishing the new order-paper tokens, IBM Plex typography, redesigned admin shell, updated login screen, command-centre overview restyle, and refreshed domain landing pages for the admin frontend.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: This is an admin-frontend-only rollout, so deployment depends on Vercel picking up the latest `main` push. The next visual pass should bring the deeper workflow screens onto the same design primitives for full-system consistency.

- Date: 2026-06-03
- Request: Implement production-safe MP auth hardening with admin-assisted reset, forced password change, and lockout/session handling for launch.
- Summary: Added shared auth state fields to `users` (`must_change_password`, `password_reset_by_admin_at`, `password_changed_at`, `force_password_reason`, `failed_login_attempts`, `locked_until`) plus additive DB startup migrations. Wired MP auth endpoints for change-password and forced-reset completion, blocked forced-reset users from normal dashboard APIs, added login lockout handling, and made MP login/session helpers respect forced-reset and session-expiry notices. Added a dedicated `/force-password-reset` page, dashboard guard, settings re-login flow, and admin account tooling for temporary password resets plus status visibility. Added backend regression coverage for admin reset, forced-reset blocking/completion, and login lockout.
- Files touched: `sansadx_backend/db.py`, `api_router.py`, `admin_api.py`, `frontend/lib/api.js`, `frontend/lib/auth.js`, `frontend/app/page.js`, `frontend/app/force-password-reset/page.js`, `frontend/app/dashboard/layout.js`, `frontend/app/dashboard/settings/page.js`, `admin/components/admin-domains/accounts/ProfileEditorPage.jsx`, `admin/components/admin-domains/accounts/CreateAccountPage.jsx`, `tests/test_auth_password_flows.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is the launch-safe password baseline without email/OTP infrastructure. The next auth step after launch should be richer session warning UX and, if required later, self-serve reset channels. Keep the current admin-assisted flow as the single source of truth until that infrastructure is intentionally added.

- Date: 2026-06-04
- Request: Push the MP password-reset hardening rollout to GitHub for deployment.
- Summary: Pushed commit `643453fc` (`Implement MP password reset hardening`) to `origin/main`, publishing the admin-assisted temporary-password flow, first-login and admin-reset forced password change, dashboard/API blocking until reset completion, clean post-change sign-out, login lockout enforcement, and admin account password-reset state/status tooling. This `main` push is intended to trigger the backend EC2 deploy workflow and the connected frontend/admin Vercel deploys.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: `tenant_overrides.json` remained intentionally unpushed because it was unrelated to the auth rollout. After the deploy finishes, the highest-value smoke checks are MP login with a forced-reset account, forced-reset completion, normal dashboard re-entry, and one admin-issued temporary password reset from the Accounts UI.

- Date: 2026-06-04
- Request: Implement real add actions for the dashboard `Today · Schedule` card so users can add schedule items, notes, and calendar links.
- Summary: Replaced the static mocked `Today · Schedule` card with a tenant-scoped dashboard engagement system backed by the new `dashboard_engagements` table and `/api/dashboard/engagements` API endpoints. The MP dashboard now supports inline creation of `schedule`, `note`, and `calendar` entries, displays saved items for the current day, and allows removing them from the card. Added focused backend API coverage for create/list/delete and a dashboard frontend regression asserting the new add actions render. Verified with `venv/bin/python -m pytest tests/test_dashboard_engagements_api.py -q`, `PATH=/opt/homebrew/bin:$PATH npm run test --prefix frontend -- --run tests/dashboard.test.jsx`, and `PATH=/opt/homebrew/bin:$PATH npm run build --prefix frontend`.
- Files touched: `sansadx_backend/db.py`, `api_router.py`, `frontend/components/dashboard/DashboardEngagementsCard.jsx`, `frontend/tests/dashboard.test.jsx`, `tests/test_dashboard_engagements_api.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is intentionally a lightweight schedule system, not a full office calendar platform. The next expansion path, if needed, would be editing/reordering items or syncing external calendars, but the current implementation already removes the mock-only blocker and stays tenant-safe.

- Date: 2026-06-08
- Request: Change the aspirant MP frontend palette from charcoal to warm brown `#A27246` and push it.
- Summary: Updated both the backend auth/session theme payload and the shared sidebar theme helper so aspirant MP/MLA accounts now use `#A27246` instead of `#242424`, while elected Lok Sabha/MLA and Rajya Sabha colors remain unchanged. Also updated project memory to reflect the new durable palette rule. Verification: `PATH=/opt/homebrew/bin:$PATH npm run build --prefix frontend`.
- Files touched: `api_router.py`, `frontend/lib/account.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Users may need to sign out and back in before all non-sidebar surfaces pick up the refreshed aspirant `theme_color` from their stored session.

- Date: 2026-06-08
- Request: Change the aspirant MP frontend palette from blue to charcoal `#242424` and push it.
- Summary: Updated both the backend auth/session theme payload and the shared sidebar theme helper so aspirant MP/MLA accounts now use `#242424` instead of `#0B3C5D`, while elected Lok Sabha/MLA and Rajya Sabha colors remain unchanged. Also updated project memory to reflect the new durable palette rule. Verification: `PATH=/opt/homebrew/bin:$PATH npm run build --prefix frontend`.
- Files touched: `api_router.py`, `frontend/lib/account.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Users may need to sign out and back in before all non-sidebar surfaces pick up the refreshed aspirant `theme_color` from their stored session.

- Date: 2026-06-08
- Request: Push the aspirant charcoal palette update to GitHub for deployment.
- Summary: Pushed commit `97f15162` (`Set aspirant palette to charcoal`) to `origin/main`, publishing the aspirant color update so the backend auth/session theme payload and the shared sidebar theme helper now use `#242424` for aspirant MP/MLA accounts.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Unrelated local edits in `data/geography/Ghaziabad/Loni.json` and `tenant_overrides.json` remained intentionally unpushed. Users may need to sign out and back in before all stored-session surfaces reflect the refreshed aspirant theme color.

- Date: 2026-06-08
- Request: Make the MP frontend sidebar account-aware so elected Lok Sabha MPs and elected MLAs use `#003B2A`, elected Rajya Sabha MPs use `#800000`, and aspirants use `#0B3C5D`.
- Summary: Added a shared sidebar theme helper in `frontend/lib/account.js` and updated `frontend/components/Sidebar.js` to derive its rail/backdrop/active/avatar/status colors from account context instead of the previous hardcoded blue. Verified with `PATH=/opt/homebrew/bin:$PATH npm run build --prefix frontend`.
- Files touched: `frontend/lib/account.js`, `frontend/components/Sidebar.js`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This currently scopes the account-aware palette to the sidebar chrome only. Other frontend surfaces that still use `user.theme_color` or green defaults should be reviewed separately if you want full cross-app color parity by account type.

- Date: 2026-06-08
- Request: Push the account-aware MP sidebar color matrix to GitHub for deployment.
- Summary: Pushed commit `c6c238f4` (`Add account-aware sidebar colors`) to `origin/main`, publishing the shared sidebar-theme helper and the MP frontend sidebar rail logic that now distinguishes elected Lok Sabha/MLA (`#003B2A`), elected Rajya Sabha (`#800000`), and aspirant MP/MLA (`#0B3C5D`) accounts.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Unrelated local edits in `data/geography/Ghaziabad/Loni.json` and `tenant_overrides.json` remained intentionally unpushed. This release changes the sidebar chrome only; broader app surfaces still using `user.theme_color` may need a separate parity pass later if you want the full product to follow the same account-aware palette.

- Date: 2026-06-08
- Request: Give aspirant accounts a distinct blue MP-frontend theme instead of reusing only the Lok Sabha / Rajya Sabha house colors.
- Summary: Updated the backend auth payload builder so `account_stage = aspirant` now emits `theme_color = #0B3C5D`, while elected accounts keep the existing Lok Sabha green and Rajya Sabha red mapping. Also recorded the new durable theming rule in project memory. Verification: `PATH=/opt/homebrew/bin:$PATH npm run build --prefix frontend`.
- Files touched: `api_router.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: Any frontend surface that still hardcodes green instead of reading `user.theme_color` should be migrated in future passes, but the main authenticated MP shell should now pick up the aspirant blue automatically after the next login/session refresh.

- Date: 2026-06-08
- Request: Push the aspirant theme-color change to GitHub.
- Summary: Pushed commit `9a1b21c2` (`Add aspirant theme color`) to `origin/main`, publishing the account-stage-aware MP frontend theme assignment so aspirant accounts now receive `#0B3C5D` from the auth/session payload while elected accounts keep the existing Lok Sabha and Rajya Sabha colors.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: Unrelated local edits in `data/geography/Ghaziabad/Loni.json`, `frontend/components/Sidebar.js`, and `tenant_overrides.json` remained intentionally unpushed. Users may need to sign out and back in before all surfaces pick up the refreshed `theme_color` from their session payload.

- Date: 2026-06-04
- Request: Push the dashboard schedule engagements feature to GitHub for deployment.
- Summary: Pushed commit `fe6915f2` (`Add dashboard schedule engagements`) to `origin/main`, publishing the tenant-scoped `dashboard_engagements` backend, the real `Today · Schedule` dashboard card with inline `Add schedule`, `Add note`, and `Add calendar` actions, and the focused backend/frontend regression coverage for that flow. This `main` push is intended to trigger the backend EC2 deploy workflow and the connected frontend deploys.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: `tenant_overrides.json` remained intentionally unpushed because it was unrelated. The best post-deploy smoke check is creating one item of each type from the live dashboard, refreshing the page, and confirming they reappear for the same tenant and can be removed cleanly.

- Date: 2026-06-04
- Request: Let PA/staff WhatsApp text like `Meeting with Chief Minister on Wednesday at 5 PM` create dashboard schedule items instead of only being treated as case queries.
- Summary: Added a conservative multilingual staff schedule parser in `modules/staff_schedule_parser.py`, then wired the staff WhatsApp branch in `main.py` to try schedule intake before the existing case-query path. Clear schedule-like messages now save into `dashboard_engagements` and send a WhatsApp confirmation back to the PA, while ambiguous or non-schedule staff text still falls back to the older case-query flow. Also consolidated staff WhatsApp sender matching into a shared normalized helper so the schedule path and existing PA/staff intake logic use the same phone-identification behavior. Verified with `venv/bin/python -m pytest tests/test_staff_schedule_parser.py tests/test_pa_whatsapp_schedule_flow.py tests/test_dashboard_engagements_api.py -q`.
- Files touched: `main.py`, `modules/staff_schedule_parser.py`, `tests/test_staff_schedule_parser.py`, `tests/test_pa_whatsapp_schedule_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This intentionally prioritizes false-negative safety over false-positive scheduling. The next iteration, if needed, should expand language/date coverage and maybe support edits/cancellations by WhatsApp, but we should keep the current “only save when clearly schedule-like” rule so case queries and complaints are not accidentally misfiled.

- Date: 2026-06-04
- Request: Push the PA WhatsApp schedule-intake feature to GitHub for deployment.
- Summary: Pushed commit `1145946f` (`Add WhatsApp staff schedule intake`) to `origin/main`, publishing the multilingual PA/staff WhatsApp schedule parser, the staff-branch intake path that saves clear schedule-like messages into `dashboard_engagements`, the WhatsApp confirmation reply for saved schedule items, and the focused parser/integration regressions for that flow. This `main` push is intended to trigger the backend EC2 deploy workflow.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: `tenant_overrides.json` remained intentionally unpushed because it was unrelated. The best post-deploy smoke check is sending one plain English and one non-English PA message that clearly describe a meeting/reminder, then confirming both appear in the dashboard schedule for the correct tenant.

- Date: 2026-06-05
- Request: Simplify the Shared Geography workspace so admin operators see only core geography and manual corrections in the main flow.
- Summary: Reworked the tenant-aware Shared Geography workspace UI to match the simplified architecture: renamed the main upload/saved sections to `Core Geography`, kept `Manual Matching Corrections` as the only operator-facing exception layer, removed generated-alias counts from the primary tenant header, and moved `Resolver Aliases` into a collapsed `Advanced Alias Diagnostics` debug surface. Also updated the admin regression test to assert the new language and flow. Verified with `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx` and `PATH=/opt/homebrew/bin:$PATH npm run build --prefix admin`.
- Files touched: `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `admin/tests/geography.test.jsx`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: This is an information-architecture cleanup, not a resolver-behavior change. If the live tenant still sees bad matching after this UI simplification, the next step stays data/runtime diagnosis rather than more operator-surface expansion.

- Date: 2026-06-05
- Request: Push and deploy the Shared Geography workspace simplification.
- Summary: Pushed commit `76f85258` (`Simplify shared geography workspace`) to `origin/main`, publishing the operator-facing Shared Geography cleanup that promotes only `Core Geography` and `Manual Matching Corrections` in the main flow while moving alias inspection into `Advanced Alias Diagnostics`. This `main` push is intended to trigger the connected admin Vercel deploy.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: `tenant_overrides.json` and `data/geography/Ghaziabad/Loni.json` remained intentionally unpushed because they were unrelated local changes. After Vercel finishes, the best smoke check is opening the Shared Geography workspace for a tenant and confirming the advanced alias panel stays collapsed by default.

- Date: 2026-06-05
- Request: Remove generated geography aliases as a runtime layer and prepare a clean live geography reset.
- Summary: Deprecated generated `geo_alias` rows as a runtime authority. The resolver now uses manual corrections plus shared core geography only, while `auto_generate_overrides()` was converted into a purge-only compatibility hook for stale alias rows. Simplified the Shared Geography workspace wording again so the generic entry point opens tenant workspaces instead of advertising alias diagnostics, added DB helpers to purge deprecated aliases or wipe all geography data, and introduced a one-time production reset marker path in `main.py` so the first post-deploy backend boot can wipe all geography state exactly once. Verified with `venv/bin/python -m pytest tests/test_override_persistence.py tests/test_same_seat_isolation.py tests/test_geography_onboarding_api.py tests/test_geography_resolver.py -q`, `venv/bin/python -m py_compile modules/geography_resolver.py sansadx_backend/db.py admin_api.py main.py`, `PATH=/opt/homebrew/bin:$PATH npm run test --prefix admin -- --run tests/geography.test.jsx`, and `PATH=/opt/homebrew/bin:$PATH npm run build --prefix admin`.
- Files touched: `modules/geography_resolver.py`, `sansadx_backend/db.py`, `admin_api.py`, `main.py`, `admin/components/admin-domains/shared-geography/GeographyWorkspacePage.jsx`, `admin/tests/geography.test.jsx`, `tests/test_override_persistence.py`, `tests/test_same_seat_isolation.py`, `tests/test_geography_onboarding_api.py`, `tests/test_geography_resolver.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The one-time reset is intentionally destructive and aimed at production only. It will erase all shared geography plus tenant-scoped manual corrections on the first backend boot after deploy, so operators must reupload geography afterward as planned.

- Date: 2026-06-05
- Request: Push and deploy the manual-alias-only geography reset.
- Summary: Pushed commit `9fee757f` (`Reset geography to manual aliases only`) to `origin/main`, publishing the backend removal of generated alias authority, the purge-only compatibility hook for stale `geo_alias` rows, the one-time production geography reset marker in `main.py`, and the admin wording cleanup that removes alias diagnostics from the main shared-geography flow. This `main` push is intended to trigger the EC2 backend deploy workflow plus the connected admin Vercel deploy.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: `tenant_overrides.json` and `data/geography/Ghaziabad/Loni.json` remained intentionally unpushed because they were unrelated local changes. The live wipe only happens after the backend restarts on EC2 and reaches the new one-time reset code path.

- Date: 2026-06-05
- Request: Push and deploy the personal-request intake flow.
- Summary: Pushed commit `330c8971` (`Handle personal request intake separately`) to `origin/main`, publishing the new `Personal Request` intake lane for discretionary/private-help asks such as transfer requests, admission help, recommendation asks, and family/property intervention requests. This push includes the narrow classifier hook, the office-contact localized reply path, the no-location-needed intake handling, the admin `Others` bucket alignment, and the focused regression coverage for taxonomy, AI classification, and end-to-end WhatsApp intake. This `main` push is intended to trigger the EC2 backend deploy workflow.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: `tenant_overrides.json` and `data/geography/Ghaziabad/Loni.json` remained intentionally unpushed because they were unrelated local changes. Romanized Hindi citizen messages still receive the romanized office-contact template by design, following the existing localized reply script-selection behavior.

- Date: 2026-06-05
- Request: Expand intake handling for support/invitation/media/donation/suggestion/spam-style office traffic and route those messages into Briefcase `Others` without auto-reply.
- Summary: Added a deterministic silent-log category layer for `Political / Support Message`, `Community / Event Invitation`, `Media / Press Outreach`, `Donation / Sponsorship Request`, `Suggestion / Idea`, and `Spam / Promotional / Irrelevant`, then wired citizen intake to save those cases while skipping the normal WhatsApp acknowledgment. Also changed unreadable/contextless citizen media to save as `Document / Attachment Only` with `status = incomplete` and ask for more details instead of sending a generic review acknowledgment, and extended the backend/frontend Briefcase `Others` bucket definitions to include the new silent categories. Verified with `venv/bin/python -m pytest tests/test_unified_taxonomy.py -q`, `venv/bin/python -m pytest tests/test_ai_location_grounding.py -q`, `venv/bin/python -m pytest tests/test_case_buckets_api.py -q`, and `venv/bin/python -m pytest tests/test_e2e_core_flow.py -q`.
- Files touched: `sansadx_backend/unified_taxonomy.py`, `sansadx_backend/ai_engine.py`, `main.py`, `api_router.py`, `frontend/components/briefcase/briefcase-shared.jsx`, `tests/test_unified_taxonomy.py`, `tests/test_ai_location_grounding.py`, `tests/test_case_buckets_api.py`, `tests/test_e2e_core_flow.py`, `PROJECT_MEMORY.md`, `TASK_LOG.md`
- Risks or follow-ups: The silent-log detectors are intentionally narrow and keyword-based; they should be expanded carefully so real grievances do not get buried in `Others`. The Briefcase `Others` tab now recognizes these categories, but the main `All cases` view still includes them unless explicitly filtered out by product choice later.

- Date: 2026-06-05
- Request: Push and deploy the silent-log `Others` intake routing and contextless-media follow-up flow.
- Summary: Pushed commit `d41de033` (`Add silent others intake routing`) to `origin/main`, publishing the silent-log intake categories for political/support, invitation, media, donation, suggestion, and promotional/spam-like messages, the no-auto-reply behavior for those cases, the `Document / Attachment Only` incomplete-media path, and the Briefcase `Others` bucket alignment for the new logged categories. This `main` push is intended to trigger the EC2 backend deploy workflow.
- Files touched: `TASK_LOG.md`
- Risks or follow-ups: `tenant_overrides.json` and `data/geography/Ghaziabad/Loni.json` remained intentionally unpushed because they were unrelated local changes. The category detectors remain intentionally narrow and should be tuned cautiously to avoid hiding genuine grievances in the silent `Others` lane.
