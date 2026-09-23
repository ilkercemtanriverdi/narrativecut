import json
import tempfile
import unittest
from pathlib import Path

from fluxengine_video_studio.core import build, revise


class CoreSmokeTest(unittest.TestCase):
    def test_build_and_revision_with_empty_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            assets = root / "assets"
            assets.mkdir()
            output = root / "output"
            timeline = build({"title": "Smoke"}, "A short test sentence.", assets, output)
            self.assertFalse(timeline["editorial_gate"]["pass"])
            revise(output / "timeline.json", "scene-001", output / "revision-manifest.json")
            self.assertTrue((output / "revision-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
