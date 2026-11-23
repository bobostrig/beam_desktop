"""Focused, GUI-free checks for the beam calculation module."""
import unittest

from beam_calculations import Load, analyze_beam


class BeamCalculationTests(unittest.TestCase):
    def test_spec_validation_reactions_and_moment(self):
        r = analyze_beam("Simply supported", 30,
                         [Load("uniform", 2, "Downward", start=0, end=15)],
                         29000, 510, 39.4, 36)
        self.assertAlmostEqual(r.reaction_left_kip, 22.5)
        self.assertAlmostEqual(r.reaction_right_kip, 7.5)
        self.assertAlmostEqual(r.extrema["moment"]["max"], 126.5625, places=2)
        self.assertAlmostEqual(r.extrema["moment"]["max_x_ft"], 11.25, places=1)

    def test_simply_supported_center_point_load(self):
        r = analyze_beam("Simply supported", 20,
                         [Load("point", 10, "Downward", position=10)],
                         29000, 204, 33.4, 36)
        self.assertAlmostEqual(r.reaction_left_kip, 5)
        self.assertAlmostEqual(r.reaction_right_kip, 5)
        self.assertAlmostEqual(r.extrema["moment"]["max"], 50, places=1)
        self.assertAlmostEqual(r.deflection_in[0], 0, places=8)
        self.assertAlmostEqual(r.deflection_in[-1], 0, places=8)

    def test_cantilever_tip_load(self):
        r = analyze_beam("Cantilever", 10,
                         [Load("point", 1, "Downward", position=10)],
                         29000, 204, 33.4, 36)
        self.assertAlmostEqual(r.reaction_left_kip, 1)
        self.assertAlmostEqual(r.reaction_right_kip, 0)
        self.assertAlmostEqual(r.deflection_in[0], 0, places=8)

    def test_rejects_load_outside_span(self):
        with self.assertRaises(ValueError):
            analyze_beam("Simply supported", 10,
                         [Load("point", 1, "Downward", position=11)],
                         29000, 204, 33.4, 36)


if __name__ == "__main__":
    unittest.main()
