import json
import shutil
import pytest
from src.semantic.identity import model_digest, vector_generation


def test_exported_identity_survives_server_move_and_detects_changed_weights(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'model.safetensors').write_bytes(b'weights')
    (source / 'config.json').write_text('{}')
    generation = vector_generation(str(source), 'catalog')
    (source / 'atlas_generation.json').write_text(json.dumps({
        'generation': generation, 'catalog_sha256': 'catalog',
        'model_sha256': model_digest(source)}))
    deployed = tmp_path / 'deployed'
    shutil.copytree(source, deployed)
    assert vector_generation(str(deployed), 'catalog') == generation
    with pytest.raises(ValueError, match='another catalog'):
        vector_generation(str(deployed), 'new catalog')
    (deployed / 'model.safetensors').write_bytes(b'tampered')
    with pytest.raises(ValueError, match='content differs'):
        vector_generation(str(deployed), 'catalog')
