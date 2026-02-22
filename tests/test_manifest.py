import json
import os

MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__),
    "../custom_components/house_battery_control/manifest.json"
)

def test_manifest_includes_ortools():
    """Ensure the manifest accurately declares OR-Tools as a physical PIP requirement."""
    assert os.path.exists(MANIFEST_PATH), "Manifest file does not exist at expected path."

    with open(MANIFEST_PATH, "r", encoding="utf-8") as file:
        manifest_data = json.load(file)

    assert "requirements" in manifest_data, "Manifest is missing 'requirements' array."
    reqs = manifest_data["requirements"]
    
    # Assert that some form of ortools definition is in the list
    has_ortools = any(req.startswith("ortools") for req in reqs)
    
    assert has_ortools, "CRITICAL: The LP solver (lin_fsm.py) requires 'ortools', but it is missing from manifest.json requirements! Home Assistant will not install it."

