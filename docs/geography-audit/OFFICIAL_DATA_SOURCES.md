# Official Data Sources and Acquisition Assessment

**Verification date:** 19 October 2026. URLs and portal behavior can change. “Available” means a specific official artifact or download route was verified during this audit; it is not a legal opinion or a guarantee of completeness.

## Status vocabulary

- `VERIFIED_AVAILABLE`: an official artifact/download or clearly documented official delivery route was verified.
- `PARTIALLY_AVAILABLE`: only some jurisdictions, entity types, vintages or fields were verified.
- `ACCESS_RESTRICTED`: login, CAPTCHA, interactive viewer or non-public system blocks reproducible bulk retrieval.
- `NOT_FOUND`: no qualifying official artifact was verified in the audit window; not proof of non-existence.
- `NOT_APPLICABLE`: the entity class does not apply to that jurisdiction.

## Source register

### Local Government Directory (LGD), Ministry of Panchayati Raj

- **Authority/use:** best verified current identity spine for states/UTs, districts, subdistricts, blocks, villages, rural and urban local bodies and wards.
- **Artifacts:** the [LGD Download Directory](https://lgdirectory.gov.in/demo/downloadDirectory.do) exposes entity downloads, change reports, GP–village and block–village mappings, and parliamentary/assembly options. The [state-wise entity report](https://lgdirectory.gov.in/demo/reportonStatewiseEntityDetails.do) exposes coverage/counts and unmapped-entity reports. The [OGD LGD catalog](https://data.gov.in/catalog/local-government-directory-lgd) publishes downloadable/API resources under the OGD framework, including the [district directory](https://data.gov.in/resource/local-government-directory-lgd-districts).
- **Formats/access:** portal downloads include PDF/HTML/XLS/ODT and often CAPTCHA; OGD resources commonly provide CSV/ZIP/API.
- **Licence:** OGD resources are generally subject to [GODL-India](https://data.gov.in/Godl) when their metadata says so; portal-only artifacts require their own terms review.
- **Risks:** reporting snapshots change; codes can be retired; blocks and local-body relationships are not uniformly complete; portal automation may be brittle. Preserve `effective_from`, `effective_to`, status and snapshot date.

### Survey of India (SoI)

- **Authority/use:** official administrative geometry. The [portal description](https://onlinemaps.surveyofindia.gov.in/AboutPortal.aspx) advertises state/district/subdistrict and state-wise village boundary products in vector/SHP form. The [ABDB page](https://surveyofindia.gov.in/pages/administrative-boundary-data-base-abdb-) supplies nationwide administrative boundary archives and metadata.
- **Village coverage:** the [Village Boundary Database page](https://surveyofindia.gov.in/pages/village-boundary-data-base-of-entire-india) listed packages for 27 states/UTs at audit time. No package was verified there for Arunachal Pradesh, Assam, Himachal Pradesh, Jammu & Kashmir, Ladakh, Manipur, Meghalaya, Mizoram or Nagaland.
- **Formats/size:** SHP/GDB archives. SoI’s [2025 vector data catalog](https://www.surveyofindia.gov.in/UserFiles/files/Vector%20Data%20Catalog%202025%281%29.pdf) describes the national administrative/village collection as a large product (approximately 15 GB), so staged object storage and streaming validation are required.
- **Acquisition:** some products are direct downloads; others use the [Online Maps product portal](https://onlinemaps.surveyofindia.gov.in/Digital_Product_Show.aspx/Home.aspx). Keep the [portal user guide](https://onlinemaps.surveyofindia.gov.in/User_Manual/User_Guide_online_maps_portal.pdf) with the acquisition record.
- **Licence:** **LEGAL REVIEW REQUIRED.** The portal [FAQ](https://onlinemaps.surveyofindia.gov.in/FAQs.aspx) describes free availability for some boundary products, while [terms shown during acquisition](https://onlinemaps.surveyofindia.gov.in/addtocart.aspx) restrict resale/republishing. The [Geospatial Guidelines page](https://onlinemaps.surveyofindia.gov.in/GeospatialGuidelines.aspx) permits broad solution-building but does not eliminate product-specific licence obligations. “₹0” is not equivalent to open redistribution.
- **Risks:** state packages have differing vintages; metadata/code population must be checked per layer. Do not assume every feature contains an LGD code merely because some state documentation does.

### Census of India

- **Authority/use:** historical demographic and settlement reference, not the current administrative authority.
- **Artifact:** [Location Code Directory, Census 2011](https://censusindia.gov.in/nada/index.php/catalog/42648), supplied as spreadsheets with state/district/subdistrict/village/town codes. An [OGD complete village directory catalog](https://punjab.data.gov.in/catalog/complete-villages-directory-indiastatedistrictsub-district-level-census-2011) provides another official distribution route.
- **Licence:** check the metadata of the selected OGD resource; GODL applies where declared.
- **Risks:** 2011 vintage, extinct/renamed/split entities, Census towns vs statutory towns, and code systems distinct from LGD. Never overwrite current LGD identity with Census names/codes; publish a dated crosswalk.

### Election Commission of India (ECI)

- **Authority/use:** statutory electoral constituency definition, reservation and composition.
- **Artifacts:** [Delimitation Order 2008](https://www.eci.gov.in/Documents/Delimitation/DelimitationofParliamentaryAssemblyConstituenciesOrder-2008%28English%29.pdf), later jurisdiction-specific orders such as the [Assam 2023 final order](https://www.eci.gov.in/Documents/Delimitation/DELIMITATIONASSAM_UPDATED.pdf), and ECI’s [publication/delimitation library](https://www.eci.gov.in/eci-publication/). The [2024 Election Atlas](https://www.eci.gov.in/EBooks/atlas-2024/) supplies official lists, maps and statistics for 543 parliamentary constituencies.
- **Formats/access:** principally PDF/e-book/HTML, sometimes interactive search. Tables require extraction plus human verification.
- **Boundary finding:** **NOT_FOUND nationwide.** This audit did not verify an official, current, nationwide SHP/GeoJSON package for all parliamentary and assembly constituency polygons. Official maps in PDFs/viewers are not equivalent to reusable vector boundaries.
- **Licence:** no blanket open-data licence was verified for the cited electoral publications. Treat public reproduction/redistribution and derived polygon publication as **LEGAL REVIEW REQUIRED**.
- **Risks:** subsequent delimitation/orders override older texts; constituency names/numbers can repeat across vintages; PC–AC relations are legally defined and cannot be inferred only by spatial containment.

### State/UT Chief Electoral Officer (CEO) portals

- **Authority/use:** polling-station directories, electoral-roll parts, local constituency publications and election-specific notices.
- **Verified examples:** Chhattisgarh publishes assembly-wise polling-station lists on its [CEO portal](https://ceochhattisgarh.nic.in/home_en.html); Delhi provides election/revision pages and AC PDFs via its [SSR portal](https://ceodelhi.gov.in/SSR.aspx); Goa exposes an official [polling-booth viewer](https://ceogoa.nic.in/appln/uil/PollingBooths.aspx); Kerala exposes [polling-station lists](https://www.ceo.kerala.gov.in/pollingstations); Manipur provides [polling-station publications](https://ceomanipur.nic.in/pollingstation); and Puducherry provides [AC-wise polling-station pages](https://ceopuducherry.py.gov.in/ac_wise_polling_station.php?c=Mjk%3D). Additional verified examples and gaps are recorded per jurisdiction in the coverage matrix.
- **Formats/access:** PDF, scanned PDF, HTML, interactive forms, CAPTCHA and electoral-roll-part downloads. There is no stable nationwide schema or URL contract.
- **Coordinates:** **NOT_FOUND nationwide.** Public station coordinates were not verified as a national bulk dataset. Some official material indicates geotags exist inside election systems, but internal availability is not public availability.
- **Licence:** public access does not establish permission for bulk commercial reuse. Preserve individual portal terms and seek permission where no explicit open licence exists.
- **Risks:** URLs and station numbering change by revision/election; “polling station,” “polling location/building” and “part” are not always one-to-one. Addresses can include personal/institutional details; store only fields needed for the public directory.

### Department of Posts / India Post

- **Authority/use:** postal office and PIN reference. India Post publishes [PIN code lists](https://www.indiapost.gov.in/rti/pincodelist); OGD publishes the [All India PIN Code Directory](https://data.gov.in/catalog/all-india-pincode-directory-through-webservice) and a current [monthly resource](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month).
- **Boundary catalog:** OGD also lists an [All India PIN Code Boundary GeoJSON catalog](https://data.gov.in/catalog/all-india-pincode-boundary-geo-json). Each resource and update must be inspected before assuming nationwide feature completeness.
- **Licence:** OGD resources are generally GODL when declared in metadata.
- **Risks:** PIN codes and post-office service areas are routing constructs, not administrative polygons; one PIN can span multiple villages/wards/constituencies, and a place can have multiple postal interpretations. Use as enrichment/search only.

### Other official portals

- The [National Water Data Portal administrative-boundaries catalog](https://www.data.gov.in/catalog/admin-boundaries) may provide useful block/district display layers under OGD. Treat it as corroboration until the actual downloadable resources, source vintage and geometry lineage are verified.
- Bhuvan/NRSC visual services may display official layers, but a viewer or tile service is not automatically a bulk-download licence or authoritative release artifact.

## Licence decision matrix

| Source family | Commercial processing | Raw redistribution | Required action |
|---|---|---|---|
| OGD resource explicitly marked GODL | Generally permitted with attribution and non-endorsement, subject to exclusions. | Generally permitted under GODL conditions. | Store resource-level licence metadata and attribution. |
| SoI products | Potentially permitted for solutions/derivatives, but product terms matter. | Do not assume permitted. | Obtain written legal interpretation before bulk/publication. |
| ECI/CEO PDFs/viewers | Publicly readable; commercial reuse not established by access alone. | Do not assume permitted. | Preserve terms; request permission or legal review. |
| Census/other official resources | Depends on delivery channel/resource metadata. | Depends on declared licence. | Decide per artifact, never per agency name alone. |

The [data.gov.in Terms of Use](https://www.data.gov.in/terms-of-use) state the portal licensing framework; GODL allows broad worldwide use and adaptations with attribution, no endorsement and no warranty. Exclusions and resource-specific metadata still control.

## Acquisition evidence required for every artifact

Each retrieval manifest must contain source owner, canonical URL, resource identifier, portal title, jurisdiction/layer, publication and retrieval timestamps, licence URL/text hash, access method, request parameters, original filename, byte size, SHA-256, MIME/container format, CRS/encoding if known, extraction tool/version, and any CAPTCHA/manual steps. Failed and unavailable attempts should also be recorded with status and evidence.

## Phase 0 conclusion

Official data is sufficient to start a disciplined pilot, not to claim complete national coverage. LGD and SoI are the first administrative sources; ECI statutory material is the electoral authority; CEO portals are a separate state-by-state acquisition program. Third-party boundary projects can be comparison inputs only and must never silently fill an official-data gap.

