[S-PR] SCIENTIFIC REGISTER
Manuscript: docs/paper/rainier3d_paper.md (main @ d61305c, 1313 lines). Line numbers refer to that file.
Scope: prose, table and figure captions, section and run-in titles, YAML abstract. Code blocks and tables of numbers read but not scored.
Method: full read, plus grep for the lexicon (intensifiers, sentence-initial So/Now/And/But/Well, editorial nouns, evaluative adjectives). Read only; nothing rerun.
Tier feed: C5 (Presentation & Communication). Register is not pervasive: 12 candidates in about 180 kB of prose. Good / minor revision, no tier reduction.

Total register flags: 12  (colloquial 4 / journalistic 0 / emotional 1 / metaphor 6 / intensifier 1)

Flags (each: "quote" - location - category - suggested alternative):
  S-PR.1 "Neither model is right at every wavelength." - L591, Fusion with the regional models, Strategy - colloquial - "right" -> "accurate"
  S-PR.1 "it breaks the fusion invariant (0.050)" - L700, Why this parameterisation - colloquial - "breaks" -> "violates"
  S-PR.1 "but pushes Vp/Vs to 1.60-1.67 at 2-4 km" - L699, Why this parameterisation - colloquial - "pushes" -> "lowers"
  S-PR.1 "can settle which is right" - L1212, Limitations, Top 300 m - colloquial - "settle which is right" -> "determine which estimate is correct"
  S-PR.3 "the held-out scores are the fair measure" - L720, caption of tbl:models (also S-PR.6) - emotional/evaluative - "fair" -> "unbiased"
  S-PR.4 "Relocation alone does not rescue the uncalibrated three-dimensional model" - L709, Validation - metaphor - "rescue" -> "reduce the residuals of"
  S-PR.4 "The EM field sees only the top ~150 m. It cannot see the altered rock buried ..." - L579, Hydrothermal alteration - metaphor (anthropomorphism) - "sees only" -> "is sensitive only to"; "cannot see" -> "does not detect"
  S-PR.4 "one-dimensional models that know neither the topography nor the slow edifice" - L1153, Locating earthquakes - metaphor (anthropomorphism) - "know neither" -> "include neither"
  S-PR.4 "their calibration waits for near-surface observations" - L506, Calibration with the critical zone - metaphor - "waits for" -> "requires"
  S-PR.4 "The 500 older ComCat events at or above the ground wait for their picks to be cached" - L1219, Limitations, Relocated catalogue - metaphor - "wait for their picks to be cached" -> "will be relocated once their picks are cached"
  S-PR.4 "The 1D model gathers the events near sea level ... four events rise until they meet the topography mask" - L1180, What changes, Summit - metaphor (low confidence; the locator moves hypocentres, so "rise" is close to literal) - "gathers" -> "places"; "rise until they meet" -> "are placed at"
  S-PR.5 "the travel times barely constrain the top 50 m" - L505, Calibration with the critical zone - intensifier - "barely constrain" -> "weakly constrain"

Low-confidence, author's call (not counted above):
  - "they test the grids where people drill, not on the volcano" - L1006, Geohydrology, Wells - mildly conversational - "where people drill" -> "where wells are drilled". Probably owned cadence; leave unless a copy-editor objects.

S-PR.2 Journalistic nouns: PASS. None found (no headline, takeaway, story, menu, recipe, workhorse, sweet spot).
S-PR.5 Casual sentence-initial connectives: PASS. No sentence opens with So, Now, And, But or Well.
S-PR.6 Captions and section titles: PARTIAL. One caption slip (L720 "fair measure"). Run-in titles ("What changes.", "Why this parameterisation.", "All models scored the same way.", "What is not yet consistent.", "Keep hypocentres in rock.") are plain and stay.

Considered but NOT flagged (terms of art, literal use, or owned voice):
  - "digital model", "placeholder"/m1_placeholder, stage labels S0-S36, level labels L1-L3, "held-out events", "invariant test", "rebuild": profile favored_phrasing.
  - "The platform is rebuilt, never patched." (L182); "The model keeps both estimates and chooses neither." (L291): owned short emphatic sentences.
  - "deposition restarts the weathering clock" (L480): established geomorphology idiom (reset of exposure/weathering age).
  - "loads it almost optimally for right-lateral slip" (L855): Coulomb sense of optimally oriented planes.
  - "overshoots", "fast rims around slow bodies", "clamped" (L600): exact description of Gaussian high-pass ringing and projection.
  - "the table rock is too slow" (L673, L1232): author shorthand for rock with tbl:units parameters; "too slow" is a quantified statement there.
  - "S20 refuses to publish" (L1094), "refused by the service" (L1035): literal software behaviour.
  - "an invented number" (L203): literal (fabricated value), not editorial.
  - "the most hazardous volcano in the Cascade Range" (L48): cited claim (hoblitt_1998, scott_1995), not an emotional adjective.
  - "clean clone" (L162, L1094): git term. "less clearly than slope does" (L338): literal comparison, not filler.
  - "senses", "sensed to" (L567, L980): standard EM depth-of-investigation usage (contrast with S-PR.4 at L579).

LLM-tell vocabulary and em-dashes (author ban):
  - Em-dashes (U+2014): 0 in the manuscript.
  - Plain-voice list (delve, robust, crucial, leverage, comprehensive, landscape, underscore, showcase, foster, nuanced, seamless, holistic, pivotal, intricate, notably, tapestry, testament, navigate, paradigm, realm, meticulous, vital, harness, unlock, streamline, bolster, furthermore, moreover, additionally, essential): 0 hits (grep, case-insensitive).
  - En-dashes are used for numeric ranges and named pairs (Gauss-Newton, Paradise-Nisqually), which is correct typography and not covered by the ban.

Top fixes (highest confidence first):
  1. L700 "breaks the fusion invariant" -> "violates the fusion invariant"
  2. L579 "sees only ... cannot see" -> "is sensitive only to ... does not detect"
  3. L720 caption "the fair measure" -> "the unbiased measure"
  4. L1153 "know neither" -> "include neither"
  5. L591 "is right at every wavelength" -> "is accurate at every wavelength"
