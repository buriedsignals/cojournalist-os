# Translations TODO — Workspace UI (Plan 04 PR 2)

The 44 `workspace_*` keys listed below were added to all 12 language files
with the English string as a placeholder. Paraglide falls back to English at
runtime when a key is missing, so shipping with placeholders is safe. Batch-
translate when convenient.

## Keys added

```
workspace_scoutList_heading
workspace_scoutList_empty
workspace_scoutList_addButton
workspace_scoutList_groupLocation
workspace_scoutList_groupBeat
workspace_scoutList_groupPage
workspace_scoutList_groupSocial
workspace_scoutList_groupCivic
workspace_inbox_heading
workspace_inbox_searchPlaceholder
workspace_inbox_empty
workspace_inbox_loadingMore
workspace_inbox_allScouts
workspace_unitDrawer_closeLabel
workspace_unitDrawer_tabContent
workspace_unitDrawer_tabEntities
workspace_unitDrawer_tabReflections
workspace_unitDrawer_promote
workspace_unitDrawer_reject
workspace_addScout_title
workspace_addScout_step1
workspace_addScout_step2
workspace_addScout_step3
workspace_addScout_submit
workspace_addScout_cancel
workspace_templatePicker_location
workspace_templatePicker_beat
workspace_templatePicker_page
workspace_templatePicker_social
workspace_templatePicker_civic
workspace_templatePicker_locationDesc
workspace_templatePicker_beatDesc
workspace_templatePicker_pageDesc
workspace_templatePicker_socialDesc
workspace_templatePicker_civicDesc
workspace_civicTest_runButton
workspace_civicTest_found
workspace_civicTest_valid
workspace_civicTest_invalid
workspace_ingest_title
workspace_ingest_tabUrl
workspace_ingest_tabContent
workspace_ingest_submit
workspace_ingest_success
```

## Languages to translate

- da (Danish)
- de (German)
- es (Spanish)
- fi (Finnish)
- fr (French) — priority (Tom reviews)
- it (Italian) — priority (Tom reviews)
- nl (Dutch)
- no (Norwegian)
- pl (Polish)
- pt (Portuguese)
- sv (Swedish)

## Recompile after editing

```bash
cd frontend
npm run paraglide:compile
npm run check
```
