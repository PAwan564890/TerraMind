"""Read-only checkpoint inventory. Does not train, download or deserialize weights."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.core import load_settings


def main():
    settings = load_settings()
    root = settings.paths.models_dir
    print(f'Model root: {root} (exists={root.is_dir()})')
    for rel in ['language_detection/hi_ne.joblib', 'decision/thresholds.json', 'decision/domain_index.npz']:
        path = root / rel
        print(f'{"FOUND" if path.is_file() else "MISSING"}: {path}')
    for task in ['intent', 'ner']:
        run = getattr(settings, task).active_run
        summary = root / task / run / 'summary.json'
        print(f'{"FOUND" if summary.is_file() else "MISSING"}: {summary}')
        if summary.is_file():
            try:
                seed = json.loads(summary.read_text(encoding='utf-8'))['best_seed']
                directory = summary.parent / f'seed_{int(seed)}'
                for filename in ['config.json','model.safetensors','tokenizer.json','tokenizer_config.json']:
                    path = directory / filename
                    print(f'{"FOUND" if path.is_file() else "CHECK"}: {path}')
                print('Checkpoint files:', ', '.join(p.name for p in directory.iterdir()) if directory.is_dir() else 'directory missing')
            except (ValueError, KeyError, OSError) as error:
                print(f'Invalid summary: {type(error).__name__}')
    print(f'E5 encoder: {settings.embeddings.model_name}; prefix={settings.embeddings.prefix!r}; max_length={settings.embeddings.max_length}')
    print('E5 is resolved from the Hugging Face cache by Transformers; it is not a fine-tuned TerraMind checkpoint.')
    print('This inventory does not prove loadability. Start the original API and inspect /health to verify inference.')


if __name__ == '__main__':
    main()
