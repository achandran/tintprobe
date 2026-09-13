# Opt-in aesthetic fidelity

`evaluation/themes.json` opts Ithilien Dawn into `formex-reef-gmt-white-steel` via `aesthetic_profile`. Other themes receive `not_applicable`, never zero. Unknown profiles or missing roles are unavailable; missing request cells leave the total null. This score does not change execution status or strict readability gates.

The combined suite evaluates each opted-in theme after native capture. Its JSON and HTML include component scores, weights, raw CIELCh measurements, and per-width request-frame usage. The palette must expose backgrounds base/mantle/crust, foregrounds text, and accents coral. These semantic roles allow another theme to opt in without Tolkien color names.

Version 1 is an uncalibrated design interpretation, not a photographic match score. The white-dial/red-GMT/solid-link steel reference URL is recorded. The black ceramic bezel and solid-link steel bracelet are required; approved reference images remain pending; no image pixels have been sampled. Before calling this calibrated, freeze those references and validate blinded candidate ordering with the user. Steel finish itself cannot be measured from flat colors.

Each range is [lower, upper, falloff]. Values inside receive 1; outside decrease linearly to 0 over falloff. Component scores use the weakest submeasurement. Dial: lightness and neutral chroma. Steel: neutral chroma and ordered adjacent lightness gaps base→mantle→crust. Markings: dark neutral text. Red: hue/chroma plus visible request-frame red usage. Restraint: request-frame neutral usage. The weighted total is 0–100; weights are 25/25/20/15/15. They are provisional, not fitted to competitor rankings.

Usage counts terminal cells, not screenshot pixels. A cell counts red when its background or nonblank foreground is red; neutral when both applicable colors have low chroma. Request frames exclude diffs and syntax, avoiding a penalty for functional green, amber, or diagnostic red. Frames are measured separately, with the weakest used; large frames cannot drown out smaller ones. This is limited evidence: other editing/search/selection surfaces and native Ghostty remain unmeasured. DIM and glyph coverage are not modeled.

Regression tests include yellow dial, blue steel, weak text, flat surfaces, wrong accent, absent/excess red, opt-out/missing data, and invariance to diff-color changes. These establish directional sanity, not human aesthetic validity. Optimize only after readability gates; preserve separate axes and review a shortlist rather than maximizing this scalar alone.
