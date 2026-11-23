## Platform
- Python desktop app using Tkinter, started with `python app.py`
- Calculations with numpy, kept in their own module, separate from
  the window code
- The calculation module must be importable and verifiable without launching the desktop app.
- Diagrams drawn with matplotlib, embedded in the window
# Project Specification

Project requirements and behavior will be documented here.
# Beam Designer

## Purpose
This evaluates a single simply supported or cantilever beam under point and uniform loads. It calculates reactions, shear, moment, and deflection, displays the results, and checks bending stress and deflection against specified limits. It is an educational design aid, not a complete structural design or a substitute for professional review.

## Inputs
For each load: magnitude, direction, position, and— for a uniform load—its start and end points. Also say whether multiple loads are allowed.
Units for all values, not just span.
How users select a steel or lumber member, and where its material properties come from.
Whether design limits are entered by users or supplied by the app.

## File operations
- Provide a File menu with Save and Open commands.
- Save the beam setup to a JSON file, including support type, span, selected section and its properties, deflection limit settings, and all point and uniform loads.
- Open a saved JSON file and restore the beam setup. Recalculate and display the results after opening.
- Use file dialogs with a JSON file filter, and show a clear error if a file cannot be opened or contains invalid beam data.

## Calculations
- Find support reactions using equilibrium: `ΣFy = 0` and `ΣM = 0`.
- Use standard beam equations for the selected supports and loads to calculate shear `V(x)`, bending moment `M(x)`, and deflection `v(x)`.
- Calculate maximum bending stress: `fb,max = |M|max / S`. Compare it with the selected member's allowable bending stress.
- Compare maximum deflection with `L/360`.
- Show the shear diagram, but do not check shear strength. Report pass/fail for bending and deflection only.

## Outputs
- The beam with its loads
- Separate graphs for shear, bending moment, and deflection, with labeled axes and units
- Support reaction values
- The maximum and minimum value on each graph and where each occurs
- Pass or fail for bending and deflection

## Look and feel
- Use a modern engineering-workbench style in a resizable desktop window. Keep beam analysis as the main view, with inputs on the left and the beam, diagrams, reactions, and design checks on the right.
- Use a pale blue background (`#EAF2FA`), white content panels, charcoal text (`#23272F`), and deep navy headings (`#23395B`). Use consistent spacing, restrained borders, and clear visual hierarchy.
- Use a clean sans-serif font for headings, controls, and graph labels, with consistent typography across the app.
- Distinguish the shear, moment, and deflection graphs with teal (`#2A7886`), blue (`#0072B2`), and burnt orange (`#D55E00`).
- Keep the BYU watermark visible but faint enough that it does not reduce text or diagram readability.
- Show validation states with readable pass and fail labels, not color alone.
- Open with the example beam loaded and its results visible.
- Keep Cougar Pinball available as a secondary view. Retain the animated mascot and game behavior, and provide a way to pause animations.

## Validation
imply supported, 30 ft, W18x35, uniform 2 kips/ft from 0 to 15 ft
   only: reactions 22.5 k (left) and 7.5 k (right); max moment
   126.6 kip-ft at 11.25 ft.

## Out of scope
Shear strength, bearing, connection design, load combinations, continuous beams, and buckling.

## Build stages
1. **Static mockup:** Build the single-file page layout with all inputs, example values, beam/load illustration, output cards, and labeled plot placeholders. Do not implement calculations.
2. **Input behavior:** Make support, member, material, load, unit, and design-limit controls usable. Support adding and removing point and uniform loads, and show each load on the beam illustration.
3. **Beam response:** Calculate support reactions, shear, moment, and deflection for the supported beam types and loads. Update the beam illustration and three plots when inputs change.
4. **Design checks:** Calculate maximum bending stress and compare it with the selected allowable value. Compare maximum deflection with the selected limit and show pass/fail results; do not add a shear-strength check.
5. **Validation and refinement:** Check the example against the Validation values, address edge cases for supported inputs, and refine labels, units, and the resizable desktop layout.
