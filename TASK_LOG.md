# Task Log

Chronological log of completed repository work. Read before making changes to understand recent context.

## Entry Template

- Date: YYYY-MM-DD
- Request:
- Summary:
- Files touched:
- Risks or follow-ups:

## Entries

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
